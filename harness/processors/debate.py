#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import itertools
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

from core.models import Crystal
from core.text_utils import count_output_words
from data.storage import FileIO
from external.ai_client import AIClient, aggregate_call_log
from external.fetcher import ExternalFetcher
from external.summary import extract_keywords, summarize_items, summarize_role_answer, summarize_text
from governance.config import Config
from governance.services import load_audit_rules, load_role_ideologies
from harness.alarm import AlarmMonitor
from harness.engine import CrystalEngine
from harness.evidence import EvidenceOrchestrator
from harness.rumad import RUMADController


def _is_reliable_output(answer: str) -> bool:
    """判断角色输出是否可靠：无错误标记/占位符，且以正常标点或代码块收尾。"""
    tail = answer.rstrip()
    return bool(tail) and not answer.startswith(("错误", "AI调用失败")) \
        and not any(m in answer for m in ("待补充", "占位", "TODO")) \
        and (tail.endswith("```") or tail[-1] in "。！？!?；;…”’\"'）)]*`")


_CONTEXT_LABEL_RE = re.compile(r"【[^】]{0,24}】|用户[:：]|助手[:：]|系统[:：]|AI[:：]")
_CONTEXT_STOP_WORDS = frozenset({
    "上下文", "会话", "用户", "助手", "系统", "最近", "背景", "问题",
    "要求", "请", "回答", "输入", "输出", "以下", "上述", "内容",
})


LogFn = Callable[[str, str], None]

ROUND_HISTORY_MAX_CHARS = int(Config.CONVERGENCE_CONFIG["history_max_chars"])
ROUND_HISTORY_PER_ROLE_MIN = int(Config.CONVERGENCE_CONFIG["history_per_role_min"])
ROUND_HISTORY_PER_ROLE_MAX = int(Config.CONVERGENCE_CONFIG["history_per_role_max"])
ROLE_BRIEF_MAX_CHARS = int(Config.CONVERGENCE_CONFIG["role_brief_max_chars"])
QIANFAN_QUERY_COUNT = 4
QIANFAN_PER_QUERY_RESULTS = 5
QIANFAN_RAW_MAX_CHARS = 10000
QIANFAN_SUMMARY_ITEMS = 14
QIANFAN_PER_ITEM_CHARS = 200
BIAS_MARKERS = ("毫无疑问", "显然", "必然", "必定", "完全否定", "一边倒", "偏激", "偏见", "不容置疑")


def compute_bias_amplification(round_answers: List[Dict]) -> float:
    """按回答中强立场/偏激标记占比估算偏见强化指数（0-1）。"""
    total = max(1, len(round_answers or []))
    biased = sum(
        1 for item in (round_answers or [])
        if re.search("|".join(BIAS_MARKERS), item.get("answer", "") or "")
    )
    return biased / total

try:
    from harness.orchestrator import OutputOrchestrator
except ImportError:
    OutputOrchestrator = None

try:
    from harness.assurance.day12_integration import Day12Integration
except ImportError:
    Day12Integration = None

try:
    from harness.contemplative import ContemplativeEngine
except ImportError:
    ContemplativeEngine = None

@dataclass
class DebateContext:
    """辩论运行时上下文（线程隔离）"""
    current_question: str = ""
    routing_result: dict = field(default_factory=dict)
    current_classification: dict = field(default_factory=dict)
    cognitive_operators: str = "[思维模式：平衡]"
    history_result: dict = field(default_factory=dict)
    reused_crystals: list = field(default_factory=list)
    forced_perspective: str = ""
    external_has_new: bool = False
    start_time: float = 0.0
    token_count: int = 0
    role_external_cache: dict = field(default_factory=dict)
    audit_external_context: str = ""
    last_round_answers: list = field(default_factory=list)
    evidence_package: Any = None
    evidence_orchestrator: Any = None
    
    # === Day 4 新增：晶体缓存与状态 ===
    crystal_cache: list = field(default_factory=list)      # 检索到的晶体对象列表
    is_crystal_cached: bool = False                        # 缓存是否已填充
    current_round: int = 0                                 # 当前轮次
    last_audit_score: float = 0.0                          # 上一轮审计均分
    audit_history: list = field(default_factory=list)      # 所有轮的审计记录
    # === Day 5 新增：历史压缩 ===
    round_summaries: dict = field(default_factory=dict)    # {round_no: "300字摘要"}
    full_history_loaded: bool = False                      # 是否已加载完整历史
    # === Day 8 新增：法官提前介入 ===
    arbitration: str = ""                                  # 大法官仲裁意见
    arbitration_round: int = 0                             # 仲裁发生在第几轮前
    conflict_streak: int = 0                               # 连续 major_conflict 轮数
    judge_early_called: bool = False                       # 本轮辩论是否已提前介入
    # === Day 10 新增：缺口诊断 ===
    gap_diagnostics: dict = field(default_factory=dict)
@dataclass   
class DebateRole:
    key: str
    name: str
    instruction: str

class DebateEngine:
    """多角色辩论引擎 —— 并发提速版（含百灵鸟、每轮反思、流式输出、进度回调）"""

    ROLE_ATTENTION_PROFILES = {
        "radical": {
            "label": "破局采样",
            "keywords": "破局 非共识 机会 创新 反例 假设 颠覆 新路径",
            "sample_a": "优先追求洞察强度、非显然视角和破局可能",
            "sample_b": "优先追求突破方案的可落地路径、失败条件和反证检查",
        },
        "conservative": {
            "label": "边界采样",
            "keywords": "风险 成本 约束 边界 失败 安全 稳健 验证",
            "sample_a": "优先寻找风险、限制、成本和不可忽略的边界条件",
            "sample_b": "优先构造稳健执行方案、验证步骤和最低可行路径",
        },
        "structural": {
            "label": "结构采样",
            "keywords": "结构 因果 系统 流程 模型 类比 关系 分层",
            "sample_a": "优先抽取问题结构、因果链条和关键变量",
            "sample_b": "优先建立分步流程、评价标准和可复用模型",
        },
        "executor": {
            "label": "执行采样",
            "keywords": "步骤 行动 资源 时间 优先级 检查点 任务 交付",
            "sample_a": "优先拆解行动路径、资源需求和最小可执行步骤",
            "sample_b": "优先检查执行阻力、时间顺序和验收标准",
        },
        "auditor": {
            "label": "审计采样",
            "keywords": "证据 漏洞 冲突 过度推断 验证 反例 暂存 不确定",
            "sample_a": "优先寻找证据缺口、逻辑漏洞和过度推断",
            "sample_b": "优先提出验证办法、暂存问题和纠偏建议",
        },
        "default": {
            "label": "角色采样",
            "keywords": "问题 证据 结构 风险 行动 反思",
            "sample_a": "优先寻找本角色最强洞察和独特贡献",
            "sample_b": "优先检查本角色观点的证据、边界和执行条件",
        },
        "lark": {
            "label": "知识广度采样",
            "keywords": "外部知识 前沿动态 多领域 跨学科 最新论文 行业实践",
            "sample_a": "学术视角：优先引用最新论文和理论框架",
            "sample_b": "产业视角：优先引用行业案例和落地实践",
            "sample_c": "未来视角：优先提出前瞻性假设和推演",
        },
        "judge": {
            "label": "裁决采样",
            "keywords": "裁决 判决 依据 资源 原则 引证 终审",
            "sample_a": "优先审视各方论证所依据的晶体、原则和客观约束",
            "sample_b": "优先做出可追溯的终裁结论，并写明引用来源",
        },
        "spokesperson": {
            "label": "定调采样",
            "keywords": "对外 沟通 降维 明确 简洁 通俗 定调",
            "sample_a": "优先将专业黑话转化为通俗易懂的语言",
            "sample_b": "优先提炼不超过3条的核心信息，确保对外一致",
        },
        "pilgrim": {
            "label": "远航采样",
            "keywords": "长期 使命 价值观 持续 道德 愿景",
            "sample_a": "优先评估方案与长期愿景的契合度",
            "sample_b": "优先检查是否偏离核心使命，是否可持续",
        },
        "strategist": {
            "label": "奇谋采样",
            "keywords": "时机 人性 机会窗口 借力 非常规 押注",
            "sample_a": "优先寻找人性破绽和时机窗口",
            "sample_b": "优先评估方案的灵活性和迂回空间",
        },
        "statesman": {
            "label": "调研采样",
            "keywords": "调研 矛盾 全局 实事 数据 主要矛盾 求是",
            "sample_a": "优先从全局矛盾和数据分析问题",
            "sample_b": "优先提出实事求是、可落地的综合策略",
        },
    }

    def __init__(self, ai: AIClient, engine: CrystalEngine, roles: List[Dict], log: LogFn = None, stream_callback: Callable = None, progress_callback: Callable = None):
        self.ai = ai
        self.engine = engine
        self.log = log or (lambda message, level="system": None)
        self.stream_callback = stream_callback
        self.progress_callback = progress_callback

        # 确保百灵鸟存在
        role_keys = {r.get("key") for r in roles}
        if "lark" not in role_keys:
            roles.append({
                "key": "lark",
                "name": "百灵鸟",
                "instruction": "你是一位见多识广的通用智能体。你不受晶体树知识库的限制，擅长从广阔的外部世界补充信息。你在第二轮才登场，提供外部视野。"
            })

        self.roles = [
            DebateRole(str(item.get("key", idx)), item.get("name", f"角色{idx + 1}"), item.get("instruction", ""))
            for idx, item in enumerate(roles)
        ]

        # ===== Day 11.5: RUMAD 拓扑控制 =====
        self.rumad = RUMADController(
            role_names=[r.name for r in self.roles],
            learning_rate=0.1,
            discount_factor=0.9,
            epsilon=0.3
        )
        preferences = {}
        for role in self.roles:
            vote_key = f"vote_{role.key}"
            vote_value = self.engine.hebbian_weights.get(vote_key, 0.5)
            if vote_value != 0.5:
                preferences[role.name] = vote_value - 0.5
        if preferences:
            self.rumad.apply_user_preferences(preferences)
            self.log(f"🧠 用户票选已注入 RUMAD：{preferences}", "system")
        self.roles = self.rumad.prioritize_roles(self.roles)
        if self.rumad.user_preferences:
            ordered = [r.name for r in self.roles]
            self.log(f"🧠 下一场辩论优先调用顺序：{ordered}", "system")
        self.rumad_enabled = False  # 默认关闭，可通过参数启用
        
        # 存储历史数据用于 RUMAD 更新
        self._rumad_round_answers = {}
        self._rumad_audits = {}

        # Day 1 新增：警报监控系统
        self.alarm_monitor = AlarmMonitor(log_callback=self.log)
        self.alarm_triggered_this_round = False   # 标记本轮是否已触发过警报
        # Day 2.8: 元问题分类器
        try:
            import sys
            core_config_path = str(Config.DATA_ROOT / "核心配置")
            if core_config_path not in sys.path:
                sys.path.append(core_config_path)
            from question_classifier import QuestionClassifier
            self.question_classifier = QuestionClassifier()
        except ImportError:
            self.question_classifier = None
            self.log(
                "[WARN] question_classifier not found; meta question classification disabled",
                "warning",
            )
     
        # ===== 新增：缺失的属性初始化 =====
        self._forced_perspective = None     # 强制注入的对立视角
        self._external_has_new = False      # 本轮是否有新外部数据
        self._current_question = None       # 当前辩论问题
        self._routing_result = None         # 便宜门路由结果
        self._cognitive_operators = "[思维模式：平衡] [论证偏好：平衡] [输出偏好：平衡]"  # 默认认知风格
        self._current_classification = None # 元问题分类结果
        self._history_result = None         # 历史诊断结果          
        # Day 4: 历史诊断与经验复用
        self._history_result = None
        # ===== Day 10: 角色质量参数缓存 =====
        self._role_quality_cache = {}           

    # ==================== 新增：带重试的并发安全调用 ====================
    # ---- 修改：_call_role_with_retry 使用独立 AIClient ----
    def _call_role_with_retry(self, role: DebateRole, prompt: str, system: str,
                               max_retries: int = 2, max_tokens: int = None, **kwargs):
        # 兼容旧参数名 expected_words
        if 'expected_words' in kwargs:
            max_tokens = kwargs['expected_words']
        # 如果未传入 max_tokens，根据角色配置计算
        quality_config = self._get_role_quality_config(role.key)
        temperature = quality_config["temperature"]
        if max_tokens is None:
            base_tokens = 1500
            max_tokens = int(base_tokens * quality_config.get("token_multiplier", 1.0))

        self.log(f"  🔧 {role.name}: temp={temperature:.2f}, max_tokens={max_tokens}", "system")

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                ai_client = AIClient(api_key=self.ai.api_key)
                result = ai_client._call_api(
                    [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    caller=f"role:{role.key}",
                )

                if result is None:
                    raise Exception("AI返回为空（None）")
                if not isinstance(result, str):
                    raise Exception(f"AI返回类型异常: {type(result)}")
                if result.strip() == "":
                    raise Exception("AI返回空字符串")
                if result.startswith("错误：") or result.startswith("AI调用失败"):
                    raise Exception(result)

                # ===== Day 4 修改：检测截断 → 触发补充（不重试） =====
                if self._is_severely_truncated(result, max_tokens):
                    self.log(f"  ⚠️ {role.name} 输出疑似截断（{count_output_words(result)}字），触发续写补充...", "warning")
                    # 调用补充接口（只传当前回答，不传全上下文）
                    supplement_prompt = f"你的回答不够完整，请继续补充完善以下内容（不要重复已有内容，直接续写）：\n\n{result}"
                    supplement = ai_client.chat(supplement_prompt, system=system, temperature=temperature)
                    if supplement and len(supplement) > 10:
                        # 合并结果
                        result = result + "\n\n" + supplement
                        self.log(f"  ✅ {role.name} 补充完成，总字数 {count_output_words(result)}", "system")
                    else:
                        self.log(f"  ⚠️ {role.name} 补充生成失败，返回原回答", "warning")
                return result

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    self.log(f"⚠️ {role.name} 调用失败 (尝试 {attempt+1}/{max_retries+1})，{wait_time}s 后重试...", "warning")
                    time.sleep(wait_time)
                else:
                    error_msg = f"{role.name} 在 {max_retries} 次重试后仍失败: {last_error}"
                    self.log(f"❌ {error_msg}", "error")
                    return f"（{role.name} 发言失败: {str(last_error)[:50]}）"

        return f"（{role.name} 发言超时）"

    # ===== Day 10: 角色质量参数 =====
    def _get_role_quality_config(self, role_key: str) -> Dict[str, Any]:
        """获取角色的质量参数配置"""
        # 使用缓存避免重复查找
        if role_key in self._role_quality_cache:
            return self._role_quality_cache[role_key]
        
        config = Config.ROLE_QUALITY_CONFIG.get(
            role_key,
            Config.ROLE_QUALITY_CONFIG.get("default", {})
        )
        result = {
            "temperature": config.get("temperature", 0.70),
            "token_multiplier": config.get("token_multiplier", 3.0)
        }
        self._role_quality_cache[role_key] = result
        return result

    def _is_severely_truncated(self, text: str, expected_words: int) -> bool:
        """检测是否严重截断：只认显式截断标记与未闭合代码块，避免因长度误触发第二次调用。"""
        text = (text or "").strip()
        output_words = count_output_words(text)
        if output_words < 100:
            return False
        tail = text[-40:]
        return any((
            any(marker in tail for marker in ("…", "...", "未完", "待续", "待更新", "（待续）", "```")),
            text.count("```") % 2 == 1,
        ))

    # ==================== 辅助方法 ====================
    def _estimate_complexity(self, question: str) -> float:
        q_len = len(question)
        length_score = min(1.0, q_len / 150)
        complex_keywords = [
            "设计", "方案", "系统", "模型", "策略", "框架",
            "博弈", "全球", "长期", "多变量", "优化", "权衡",
            "机制", "制度", "政策", "评估", "比较", "综合"
        ]
        keyword_score = sum(1 for kw in complex_keywords if kw in question) / 5.0
        keyword_score = min(1.0, keyword_score)
        open_score = 0.3 if any(kw in question for kw in ["如何", "为什么", "怎样", "设计"]) else 0.0
        final = 0.4 * length_score + 0.4 * keyword_score + 0.2 * open_score
        return min(1.0, final)
  

    def _truncate_to_sentence(self, text: str, max_len: int = 1200) -> str:
        if len(text) <= max_len:
            return text
        search_start = max(0, max_len - 50)
        search_end = min(len(text), max_len + 50)
        segment = text[search_start:search_end]
        match = re.search(r'[。！？；；.!?;]', segment)
        if match:
            cut_pos = search_start + match.start() + 1
            return text[:cut_pos] + "……（后略）"
        else:
            return text[:max_len] + "……（后略）"

    def _emit_progress(self, stage: str, progress: int):
        if self.progress_callback:
            self.progress_callback({
                "stage": stage,
                "progress": min(100, max(0, progress)),
                "timestamp": datetime.now().isoformat()
            })

    # ==================== 外部知识相关 ====================
    def _fetch_external_overview(self, question: str) -> str:
        prompt = f"""请作为一个见多识广的通用智能体，为以下问题提供一份「外部知识总览」。

【用户问题】
{question}

【要求】
1. 提供 3~5 个来自不同领域（学术、产业、政策、跨学科）的最新案例或理论。
2. 每个案例用 1~2 句话说明其核心观点。
3. 最后用一句话总结：这些外部知识如何可能补充或挑战传统认知。

【输出格式】纯文本，不超过 500 字。不要使用 Markdown 或 JSON。

【语言要求】必须使用中文，专有名词可保留英文但需加中文注释。
"""
        if Config.ENABLE_BAIDU_QIANFAN:
            try:
                fetcher = ExternalFetcher(log_callback=self.log, file_io=FileIO)
                queries = self._generate_qianfan_queries(question)
                all_items = []
                seen_titles = set()
                for query in queries:
                    items = fetcher.fetch_qianfan(query, max_results=QIANFAN_PER_QUERY_RESULTS)
                    for item in items:
                        title = (item.get("title") or "").strip()
                        if not title or title in seen_titles:
                            continue
                        seen_titles.add(title)
                        all_items.append(item)
                if all_items:
                    material = "\n".join(
                        f"- {item['title']}: {item['summary']}（{item['link']}）"
                        for item in all_items
                    )
                    if len(material) > QIANFAN_RAW_MAX_CHARS:
                        material = material[:QIANFAN_RAW_MAX_CHARS]
                    raw_chars = len(material)
                    if Config.QIANFAN_OVERVIEW_MODE == "extractive":
                        setattr(self, "_last_qianfan_raw", material)
                        setattr(self, "_last_qianfan_items", len(all_items))
                        compressed = summarize_items(
                            all_items,
                            max_items=QIANFAN_SUMMARY_ITEMS,
                            per_item_chars=QIANFAN_PER_ITEM_CHARS,
                        )
                        material = "\n".join(
                            f"- {item['title']}: {item['summary']}（{item['link']}）"
                            for item in compressed
                        )
                        setattr(self, "_external_has_new", True)
                        self.log(
                            f"🧩 千帆原始材料 {len(all_items)} 条 / {raw_chars} 字 → "
                            f"摘要 {len(material)} 字",
                            "system",
                        )
                        return (
                            "【外部知识总览（千帆检索摘要）】\n"
                            f"{material}\n"
                            "（来源：百度千帆）"
                        )
                    prompt = (
                        "【真实搜索结果】\n"
                        f"{material}\n\n"
                        f"{prompt}\n"
                        "请优先基于以上真实搜索结果组织总览，不足部分再用你的知识补充。"
                    )
                else:
                    self.log("⚠️ 百度千帆外部总览无结果，降级为模型知识生成", "warning")
            except Exception as e:
                self.log(f"⚠️ 百度千帆外部总览失败，降级为模型知识生成：{e}", "warning")
        try:
            result = self.ai.chat(prompt)
            # ← 修复：检查 result 是否有效
            if result is None:
                return "（外部知识总览暂不可用）"
            if result.startswith("错误") or result.startswith("AI调用失败"):
                return "（外部知识总览暂不可用）"
            if not result.strip():
                return "（外部知识总览暂不可用）"
            self._external_has_new = True
            return result.strip()
        except Exception as e:
            self.log(f"[WARN] 外部知识总览生成失败：{e}", "warning")
            return "（外部知识总览暂不可用）"

    def _generate_qianfan_queries(self, question: str) -> List[str]:
        """生成千帆检索查询词：DeepSeek 优先，失败降级到 jieba + 角色词。"""
        queries = [question.strip()]
        try:
            prompt = (
                "请为以下问题生成 2-3 条补充搜索查询，用于在百度上检索真实资料。"
                "要求覆盖学术、产业/案例、政策等不同视角，不要重复原问题。"
                "只返回 JSON：{\"queries\": [\"查询1\", \"查询2\", \"查询3\"]}\n\n"
                f"问题：{question}"
            )
            raw = self.ai.chat_json(prompt, temperature=0.2)
            for item in (raw.get("queries") or []):
                query = str(item).strip()
                if query and query not in queries and len(query) >= 4:
                    queries.append(query)
                if len(queries) >= QIANFAN_QUERY_COUNT:
                    break
        except Exception as e:
            self.log(f"⚠️ 千帆查询词生成失败，使用本地降级：{e}", "warning")
        if len(queries) < 2:
            queries.extend(self._fallback_qianfan_queries(question))
        return queries[:QIANFAN_QUERY_COUNT]

    def _fallback_qianfan_queries(self, question: str) -> List[str]:
        """jieba TextRank + 角色词组成的本地查询词兜底。"""
        try:
            keywords = extract_keywords(question, top_k=8)
        except Exception:
            keywords = []
        words = [w for w in keywords if len(w) > 1]
        suffixes = ["案例", "政策", "学术论文"]
        queries = [
            f"{word} {suffixes[idx % len(suffixes)]}"
            for idx, word in enumerate(words[:6])
        ]
        for key in ("radical", "conservative", "lark"):
            profile = self.ROLE_ATTENTION_PROFILES.get(key, {})
            for kw in str(profile.get("keywords", "")).split()[:2]:
                if kw and kw not in queries:
                    queries.append(kw)
        return list(dict.fromkeys(queries))[:3]

    # ===== 修改：百灵鸟直接输出综合视角（删除三样本采样+合成）=====
    # ===== 修改：百灵鸟直接输出综合视角（删除三样本采样+合成）=====
    def _lark_sampled_opinion(self, question: str, external_overview: str) -> Dict:
        """
        百灵鸟直接输出综合外部视角（原三样本采样+合成已删除，提速约3.8倍）
        """
        self.log("🎵 百灵鸟正在生成综合外部视角...", "system")
        
        lark_role = DebateRole(key="lark", name="百灵鸟", instruction="见多识广的通用智能体")
        
        prompt = f"""
【用户问题】{question}

【外部知识总览】
{external_overview}

你正在进行百灵鸟的角色输出。请提供200-300字的综合外部视角，
包含学术、产业、未来三个维度的洞察：
- 学术维度：引用最新论文或理论框架
- 产业维度：引用行业案例或实践
- 未来维度：提出前瞻性假设或推演

直接输出综合版本，不要分三部分写作。
"""
        system = self._role_system(lark_role, self._crystal_context(question))
        answer = self._call_role_with_retry(lark_role, prompt, system, max_tokens=250)
        # ← 修复：检查返回值是否为错误信息
        if answer.startswith("（") and "失败" in answer:
            return {"role": "百灵鸟", "answer": f"（百灵鸟视角暂时无法生成）\n\n{answer}"}
        return {"role": "百灵鸟", "answer": answer}

    def _get_or_create_role_external(self, role, question: str) -> str:
        """
        获取或生成该角色的专属外部简报（缓存感知）。
        每个角色针对同一个问题，只生成一次简报，后续轮次直接复用。
        """
        cache_key = f"{role.key}_{hash(question)}"
        
        # 检查缓存
        if hasattr(self, 'ctx') and cache_key in self.ctx.role_external_cache:
            cached = self.ctx.role_external_cache[cache_key]
            self.log(f"♻️ [缓存命中] {role.name} 专属简报复用", "system")
            return cached
        
        # 生成关键词
        keywords = self._generate_role_search_intent(role, question)
        if not keywords:
            keywords = ["相关外部信息"]  # 保底
        
        # 获取简报
        brief = self._fetch_role_specific_external(role, keywords, question)
        if not brief or len(brief) < 20:
            brief = f"（基于关键词 {', '.join(keywords[:2])} 的外部信息暂不可用，请依赖内部推理）"
        elif len(brief) > ROLE_BRIEF_MAX_CHARS:
            compressed_brief = summarize_text(brief, ROLE_BRIEF_MAX_CHARS)
            if compressed_brief:
                brief = compressed_brief
            self.log(f"🧩 [简报限长] {role.name} 专属简报压缩到 {len(brief)} 字", "system")
        
        # 存入缓存
        if hasattr(self, 'ctx'):
            self.ctx.role_external_cache[cache_key] = brief
            self.log(f"🧩 [缓存写入] {role.name} 专属简报已生成（关键词：{', '.join(keywords[:3])}）", "system")
        
        return brief

    def _fetch_role_specific_external(self, role: DebateRole, keywords: List[str], question: str) -> str:
        # ===== 优先复用证据包，避免每角色重复网络抓取 =====
        package = getattr(self.ctx, "evidence_package", None) if hasattr(self, "ctx") else None
        if package and package.items:
            role_keywords = [kw.lower() for kw in keywords if kw]
            matched = []
            for item in package.items:
                text = f"{item.title} {item.content}".lower()
                if any(kw in text for kw in role_keywords[:3]):
                    matched.append(item.format_prompt(120))
            if matched:
                return "\n".join(matched[:3])

        try:
            if Config.ENABLE_BAIDU_QIANFAN:
                fetcher = ExternalFetcher(log_callback=self.log, file_io=FileIO)
                qianfan_results = fetcher.fetch_qianfan(
                    keywords[0] if keywords else question,
                    max_results=2,
                )
                if qianfan_results:
                    return "\n".join(
                        [
                            f"- {r.get('title', '')}: {r.get('summary', '')[:120]}"
                            for r in qianfan_results
                        ]
                    )
                self.log("⚠️ 百度千帆简报失败/为空，使用证据包兜底", "warning")
        except Exception as e:
            self.log(f"⚠️ 百度千帆简报失败：{e}", "warning")

        if package and package.items:
            return "\n".join(item.format_prompt(120) for item in package.items[:3])
        return "（未获取到该角色的专属外部信息）"

    def _generate_role_search_intent(self, role: DebateRole, question: str) -> List[str]:
        """根据角色立场和问题，生成专属搜索关键词（jieba 提取 + 过滤上下文标记）。"""
        role_keywords = {
            "radical": ["颠覆性", "创新", "变革", "未来趋势", "突破性进展"],
            "conservative": ["风险", "成本", "稳定性", "成熟方案", "行业标准"],
            "structural": ["系统", "结构", "框架", "同构", "模型"],
            "judge": ["衡量标准", "评估框架", "决策依据", "专家共识"],
            "spokesperson": ["执行方案", "落地路径", "决策要点", "优先级"],
            "lark": ["前沿", "交叉领域", "新兴趋势", "外部视角", "跨界案例"],
            "pilgrim": ["长期", "使命", "愿景", "价值观", "代际"],
            "strategist": ["机会窗口", "时机", "非常规", "博弈", "杠杆"],
            "statesman": ["实事求是", "主要矛盾", "统筹", "实践", "群众"],
            "ecologist": ["生态", "可持续", "长期影响", "系统效应"],
            "pragmatist": ["实际案例", "落地数据", "ROI", "可行性", "量化指标"],
            "executor": ["执行", "落地", "步骤", "资源", "排期"],
            "auditor": ["审计", "风险", "合规", "复核", "质量"],
        }
        base_keywords = role_keywords.get(role.key, ["相关外部信息"])
        clean_question = _CONTEXT_LABEL_RE.sub("", question or "")
        question_keywords = [
            word for word in extract_keywords(clean_question, top_k=5)
            if len(word) >= 2 and word not in _CONTEXT_STOP_WORDS
        ]
        return list(dict.fromkeys(base_keywords + question_keywords))[:5]

    # ==================== 核心方法 ====================
    def _core_roles(self) -> List[DebateRole]:
        # 返回所有非百灵鸟、非替身的角色（即除 lark 和 twin 外的所有角色）
        return [r for r in self.roles if r.key not in ("lark", "twin")]

    @staticmethod
    def _all_answers_failed(answers: List[Dict]) -> bool:
        if not answers:
            return False
        return all(
            "发言失败" in a.get("answer", "") or "生成失败" in a.get("answer", "")
            for a in answers
        )


    def _assign_roles_dynamically(self, question: str, candidate_roles: List[DebateRole]) -> List[DebateRole]:
        """
        动态角色分配（PEAR + 元辩论）
        通过两阶段元辩论，为每个发言位置选择最合适的角色。
        
        返回：按发言位置顺序排列的角色列表（长度固定，与候选角色数量一致）
        """
        if len(candidate_roles) < 2:
            return candidate_roles
        
        # ---- 阶段1：提案 ----
        # 每个角色生成一份针对当前问题的定制论点
        proposals = {}
        for role in candidate_roles:
            prompt = f"""
用户问题：{question}

请以【{role.name}】的立场，简要阐述你对这个问题的核心论点（不超过200字）。
你的观点必须体现你的角色特征。
"""
            try:
                response = self.ai.chat(prompt, system=f"你是{role.name}，请给出你的核心论点。")
                proposals[role.key] = {"role": role, "proposal": response}
                self.log(f"  提案生成：{role.name}", "system")
            except Exception as e:
                self.log(f"  提案生成失败({role.name}): {e}", "warning")
                proposals[role.key] = {"role": role, "proposal": f"（{role.name}的论点生成失败）"}
        
        # ---- 阶段2：同行评审 ----
        # 每个角色对其他角色的提案进行评分（0-10）
        scores = {role.key: 0 for role in candidate_roles}
        for role in candidate_roles:
            reviewer = role
            review_text = ""
            for target_key, proposal_data in proposals.items():
                if target_key == role.key:
                    continue
                target_name = proposal_data["role"].name
                target_proposal = proposal_data["proposal"]
                review_text += f"【{target_name}的提案】\n{target_proposal}\n\n"
            
            if not review_text:
                continue
            
            prompt = f"""
用户问题：{question}

你作为【{reviewer.name}】，请对以下其他角色的提案进行评分（0-10分）。

{review_text}

请输出 JSON 格式（只输出JSON，不要其他内容）：
{{
    "scores": {{
        "角色名1": 分数,
        "角色名2": 分数,
        ...
    }},
    "justification": "简要说明你的评分依据"
}}
"""
            try:
                response = self.ai.chat_json(prompt)
                if "error" not in response and "scores" in response:
                    for name, score in response["scores"].items():
                        # 根据角色名查找key
                        for target_key, proposal_data in proposals.items():
                            if proposal_data["role"].name == name:
                                scores[target_key] += score
                                break
                self.log(f"  评审完成：{reviewer.name}", "system")
            except Exception as e:
                self.log(f"  评审失败({reviewer.name}): {e}", "warning")
                # 降级：平均分配
                for target_key in proposals:
                    if target_key != role.key:
                        scores[target_key] += 5  # 中立分
        
        # ---- 排序与分配 ----
        # 按得分降序排列角色
        sorted_roles = sorted(candidate_roles, key=lambda r: scores.get(r.key, 0), reverse=True)
        
        # 记录分配结果
        self.log("  动态角色分配结果：", "system")
        for idx, role in enumerate(sorted_roles):
            self.log(f"    位置{idx+1}: {role.name} (得分{scores.get(role.key, 0):.1f})", "system")
        
        return sorted_roles

    def generate_twin_role(self, fingerprint=None) -> DebateRole:
        """
        根据认知指纹动态生成“替身-我”角色

        替身角色的 System Prompt 会注入用户的认知指纹特征，
        使其回答风格接近用户本人的思维惯性。

        Args:
            fingerprint: CognitiveFingerprint 对象（可选，不传则自动加载）

        Returns:
            DebateRole: 替身角色
        """
        if fingerprint is None:
            try:
                fingerprint = self.engine.fingerprint_extractor.get_fingerprint()
            except Exception as e:
                print(f"[WARN] 无法获取认知指纹: {e}，使用默认替身")
                fingerprint = None

        # 构建替身角色的特征描述
        if fingerprint:
            risk_desc = "偏好高风险高回报方案" if fingerprint.risk_tolerance > 0.6 else "偏好低风险稳健方案"
            innovation_desc = "偏好颠覆性创新" if fingerprint.innovation_preference > 0.6 else "偏好渐进式优化"
            decisive_desc = "快速决断型" if fingerprint.decisiveness > 0.6 else "深思熟虑型"
            role_desc = f"最常采纳的角色是 {fingerprint.preferred_role}"
            confidence_note = f"（当前指纹置信度: {fingerprint.confidence:.2f}）"
        else:
            risk_desc = "偏好中等风险方案"
            innovation_desc = "偏好平衡创新与稳健"
            decisive_desc = "适度决断型"
            role_desc = "尚未建立明确的角色偏好"
            confidence_note = "（指纹数据不足，使用默认替身）"

        instruction = f"""你是认知晶体树辩论引擎中的【替身-我】角色。

你的任务是**复刻用户的思维惯性**，在辩论中站在用户的立场发言。

【用户认知特征】
- 风险偏好：{risk_desc}
- 创新偏好：{innovation_desc}
- 决策风格：{decisive_desc}
- {role_desc}
{confidence_note}

【辩论行为准则】
1. 你的回答应体现上述认知特征，模拟用户可能会说的话。
2. 你天然倾向于支持与用户特征一致的观点。
3. 当对方提出与用户特征相悖的观点时，你会本能地质疑。
4. 但你不应固执己见——如果对方的证据明显更强，你可以承认并吸收。
5. 你的终极目标是：帮用户找到最能代表“他”的答案，而非赢得辩论。

【特别提醒】
- 你不是在扮演一个“完美理性”的 AI，而是在扮演“这个人”的替身。
- 你不需要表现得比用户更聪明，但需要表现得像用户本人。
- 如果你的回答被用户本人认可，那就是最大成功。
"""

        return DebateRole(
            key="twin",
            name="替身-我",
            instruction=instruction
        )

    def _retrieve_crystals(self, question: str, similarity_threshold: float = 0.7) -> List[Tuple[float, Crystal]]:
        """检索晶体，返回带分数的元组列表（不格式化）"""
        all_crystals = self.engine.parse_crystals()
        if not all_crystals:
            return []
        task_types = self.engine._classify_question(question)
        ranked = self.engine.rank_crystals(question, all_crystals, top_k=10, task_types=task_types)
        filtered = [(score, c) for score, c in ranked if score >= similarity_threshold]
        return filtered

    def _format_crystal_context(self, crystal_list: List[Tuple[float, Crystal]]) -> str:
        """格式化晶体元组为上下文字符串"""
        if not crystal_list:
            return ""
        lines = []
        for score, crystal in crystal_list:
            lines.append(f"- [{crystal.id}] (相关性 {score:.2f}) {crystal.content}")
        return "\n".join(lines)

    def _crystal_context(self, question: str, similarity_threshold: float = 0.7) -> str:
        """保留原方法名（兼容旧调用）"""
        crystals = self._retrieve_crystals(question, similarity_threshold)
        return self._format_crystal_context(crystals)

    def _get_cached_crystal_context(self, question: str) -> str:
        """带缓存的晶体上下文获取（利用已有的 ctx.crystal_cache）"""
        if not self.ctx.is_crystal_cached:
            self.ctx.crystal_cache = self._retrieve_crystals(question)
            self.ctx.is_crystal_cached = True
            if self.ctx.crystal_cache:
                self.log(f"🧩 [缓存写入] 晶体缓存首次检索，共 {len(self.ctx.crystal_cache)} 条", "system")
            else:
                self.log("🧩 [缓存写入] 晶体缓存首次检索，未找到相关晶体", "system")
        else:
            self.log(f"♻️ [缓存命中] 晶体缓存复用，共 {len(self.ctx.crystal_cache)} 条", "system")
        return self._format_crystal_context(self.ctx.crystal_cache)

    # ===== Day 9: Skill 验证作为证据 =====
    def _get_skill_evidence(self, crystal_ids: List[str]) -> str:
        """
        获取 Skill 验证结果作为辩论证据
        """
        if not crystal_ids:
            return ""
        
        evidence_lines = ["【Skill 验证证据】"]
        evidence_lines.append("")
        
        validation_results = self.engine.validate_skills_batch(crystal_ids)
        for cid, result in validation_results["results"].items():
            status = "✅ 通过" if result.get("valid", False) else "❌ 未通过"
            evidence_lines.append(f"- {cid}: {status}")
            if result.get("output"):
                # 提取前两行输出作为证据摘要
                output_lines = result["output"].strip().split("\n")[:3]
                for line in output_lines:
                    if line.strip():
                        evidence_lines.append(f"  - {line.strip()}")
            if result.get("error"):
                evidence_lines.append(f"  - 错误: {result['error'][:100]}")
            evidence_lines.append("")
        
        return "\n".join(evidence_lines)
    
    def _enhance_crystal_context_with_skills(self, question: str) -> str:
        """
        增强晶体上下文：包含 Skill 验证状态
        """
        # 获取原始晶体上下文
        base_context = self._crystal_context(question)
        
        # 获取所有可用的 Skill
        all_skills = self.engine.get_all_skills()
        if not all_skills:
            return base_context
        
        # 获取与问题相关的 Skill（通过简单关键词匹配）
        relevant_skills = []
        question_lower = question.lower()
        for skill_id in all_skills:
            crystal = self.engine.get_skill_crystal(skill_id)
            if crystal:
                content_lower = crystal.content.lower()
                # 简单匹配：检查问题关键词是否出现在晶体内容中
                words = question_lower.split()
                for word in words:
                    if len(word) > 1 and word in content_lower:
                        relevant_skills.append(skill_id)
                        break
        
        if not relevant_skills:
            return base_context
        
        # 获取这些 Skill 的验证证据
        evidence = self._get_skill_evidence(relevant_skills[:5])
        
        return base_context + "\n\n" + evidence

    def _get_role_ideology(self, role_key: str) -> str:
        """返回角色的思想钢印（方法论摘要），配置 JSON 优先，内置字典兜底。"""
        ideologies = {
            # ===== 1. 激进者：破坏性创新 =====
            "radical": """
你拥有“第一性原理”与“颠覆性创新”的思想钢印。

【默认假设】现有框架之所以存在，只是因为没人敢挑战它。所有人都心照不宣但其实是错的“默认前提”，就是你的攻击目标。

【强制操作】每轮发言必须提出至少 1 个“如果反过来会怎样”的极端方案。即使方案此刻不可行，也要把“不可行的原因”作为孔洞（Hxxx）输出。

【发言禁忌】禁止说“这不可能”。必须说“在什么极端条件下，这反而会成为最优解”。
""",

            # ===== 2. 保守者：反脆弱与止损 =====
            "conservative": """
你拥有“反脆弱”与“工程稳健性”的思想钢印。

【默认假设】任何方案在真实世界中都会遭遇意外。你的任务是找到“最坏情况下，方案还能撑住吗？”

【强制操作】必须为每一个乐观估计，匹配一个“如果失败，损失有多大”的止损清单。必须明确指出“在什么条件下，应该放弃当前方案”。

【发言禁忌】禁止说“这个方案很好”。必须说“这个方案在以下 X 个风险场景下，表现如何”。
""",

            # ===== 3. 结构主义者：类比迁移与系统建模 =====
            "structural": """
你拥有“同构映射”与“系统动力学”的思想钢印。

【默认假设】所有问题在更高的抽象层次上，都与某个已有问题同构。你的任务是找到那个“已知解”的类比。

【强制操作】每轮发言必须先给出 1 个跨领域类比（如“这就像生物学的进化算法...”），然后从类比中提取系统结构（因果链、反馈回路、延迟效应）。

【发言禁忌】禁止就事论事。必须说“如果把这个问题抽象为 X 结构，那么已知的 Y 方案可以迁移过来”。
""",

            # ===== 4. 百灵鸟：外部知识注入 =====
            "lark": """
你拥有“广博视野”与“跨界联想”的思想钢印。你是一台“认知探针”，专门打破晶体树的“信息茧房”。

【默认假设】晶体树现有的知识必然存在盲区。你的任务是从外部世界（学术论文、产业动态、政策法规、跨学科理论）补充被忽略的视角。

【强制操作】每轮发言必须引用至少 1 条“外部信源”（格式：[arxiv]、[news]、[hf]、[external]），且必须说明“这条外部知识挑战或补充了晶体树的哪个默认判断”。

【发言禁忌】禁止重复已有角色的观点。你必须提供“新鲜空气”。
""",

            # ===== 5. 取经者：使命锚定与长期主义 =====
            "pilgrim": """
你拥有“长期主义”与“使命锚定”的思想钢印。你是系统的“罗盘”，防止短期利益或局部优化偏离最终使命。

【默认假设】任何决策放在 10 年尺度下看，都会暴露其真实价值。你的任务是拉长时间轴。

【强制操作】发言前必须先回答：如果十年后回望，用户会感激这个选择还是后悔？你的建议必须让用户“更接近而非更远离”他的长期愿景。

【发言禁忌】禁止评价“当前效率”。必须评价“长期可持续性”。
""",

            # ===== 6. 奇谋者：时机、人性与非对称博弈 =====
            "strategist": """
你拥有“博弈论”与“机会窗口”的思想钢印。你善于洞察人心、把握时机，敢押注非常规路径。

【默认假设】正面进攻代价最高，借力打力才是上策。你的任务是找到那个“所有人都没注意到但一旦出手就能改变局面的杠杆点”。

【强制操作】每轮发言必须扫描三个维度：① 当前有哪些“可借之力”？② 现在行动 vs 等待，哪个更有利？③ 如果正面不可行，迂回路径是什么？

【发言禁忌】禁止“按部就班”。必须说“如果我们反过来利用对方的预期，会发生什么”。
""",

            # ===== 7. 延安智者：实事求是 & 矛盾分析法 =====
            "statesman": """
你拥有《毛泽东选集》方法论的核心灵魂（精要版）。你的脑回路必须按以下顺序执行：

1. **矛盾分析法**：先问“当前的主要矛盾是什么？”（全局性的、起决定性作用的）。不要被细枝末节带偏。
2. **实事求是**：结论必须基于“现有证据（晶体）”和“客观约束（资源）”。证据不足时，必须明确说“目前情况不明，建议先摸底”。
3. **群众路线**：方案必须考虑执行层的认知水平和接受度。好的战略必须是“大多数人都能听懂、能操作”的战略。
4. **持久战与根据地**：资源紧缺时不搞冒险主义，优先建立“根据地”（核心能力），以时间换空间。

【发言禁忌】禁止空谈“应该”。必须讲“在什么条件下，做什么事，能达到什么效果”。
""",

            # ===== 8. 大法官：司法三原则 =====
            "judge": """
你拥有“司法推理”与“系统宪法”的思想钢印。你是认知晶体树的“终审法院”，不是辩论者，而是“纠纷解决机制”。

【司法三原则】
1. **程序正义**：裁决必须逐项引用证据（晶体ID/孔洞ID/原则条款），不可凭直觉判案。
2. **遵循先例**：已被长期使用的晶体是“判例法”，推翻它需要双倍证据。
3. **比例原则**：驳回一个观点时，必须说明“它在什么条件下仍然可能成立”，而非全盘否定。

【外部知识锚点】参考“奥卡姆剃刀”：如无必要，勿增实体；参考“汉德公式”：只有当收益 > 风险概率 × 损失时，才应采纳激进方案。

【强制输出】裁决必须包含 `system_basis` 字段，说明判决如何回应了当前系统资源状态。
""",

            # ===== 9. 首席发言人：决策翻译官 =====
            "spokesperson": """
你拥有“认知降维”与“行动导向”的思想钢印。你是大法官裁决的“翻译官”，不是创意者，而是“执行指令的精准传声筒”。

【默认假设】老板只有 30 秒读报告，员工需要“第一步做什么”，新人需要“这跟我有什么关系”。

【三重翻译原则】
1. **老板版**：只输出“结论 + 3 条核心指令”，读完前 100 字必须能拍板。
2. **员工版**：只输出“第一步做什么、第二步做什么、第三步做什么”，不要解释为什么。
3. **新人版**：必须用一个“日常生活中的比喻”解释问题本质。

【强制约束】如果大法官的裁决中包含了 `system_basis`（资源约束依据），你必须在老板版的“决策理由”中直接引用它。不得增加任何大法官裁决之外的新建议。

【发言禁忌】禁止使用“可能”“或许”“建议”等模糊词。必须用“决定执行”“优先采用”“已驳回”等确定性表述。
"""
        }
        return load_role_ideologies().get(role_key, ideologies.get(role_key, ""))

    def _role_system(self, role: DebateRole, crystal_context: str, is_reflection: bool = False,
                     external_brief: str = "", round_num: int = 0, arbitration: str = "",
                     evidence_context: str = "") -> str:
        """
        生成角色的系统提示词
        支持按轮次注入思想钢印（完整摘要/锚点词）
        """
        try:
            # ===== 证据包注入兜底：调用方未显式传入时，从上下文复用 =====
            if not evidence_context and hasattr(self, 'ctx') and getattr(self.ctx, 'evidence_package', None):
                evidence_context = self.ctx.evidence_package.format_for_prompt()

            # ===== 公共前缀：所有角色、所有轮次字节级一致 =====
            shared_prefix = """
你是认知晶体树辩论引擎的成员。你的具体角色在下方【角色身份】中定义，必须严格扮演该角色。

辩论元能力：
1. 精准复述对方论点后再回应，禁止稻草人攻击。
2. 区分事实分歧与价值分歧，前者需举证，后者可存异。
3. 当对方证据明显更强时，必须明确承认并吸收。
4. 终极目标不是赢，而是产出融合方案，超越任何单一角色初始输出。"""

            if crystal_context and crystal_context.strip():
                shared_prefix += f"""

注意力材料（高度相关晶体）：
{crystal_context}"""
            else:
                shared_prefix += """

当前没有足够相关的晶体资料，请完全基于下方【角色身份】中的角色立场和独立推理进行论述。"""

            if evidence_context and len(evidence_context) > 20:
                shared_prefix += f"""

{evidence_context}"""

            shared_prefix += """

【强制引用】只要注意力材料或证据包提供了相关晶体（[Cxxx]），每轮发言必须引用至少 1 个 [Cxxx]，并说明支持或反驳；没有相关晶体时，必须明确写“当前无匹配晶体”。
【语言要求】全部中文，专有名词后加括号解释。
【外部证据要求】引用外部事实时必须给出可核验线索：具体日期、机构/媒体/论文来源、数字与单位（例如 [arxiv] 2026年论文、[news] 2026-08-01 路透社）。若证据包已提供 [E编号]，优先直接引用编号。禁止只写“研究表明”而不给来源。"""

            # ===== 角色专属块：同一角色跨轮次一致 =====
            role_block = f"""

【角色身份】你是认知晶体树辩论引擎中的【{role.name}】。
角色立场：{role.instruction}
"""

            # ===== 强制行为清单（保留原有逻辑） =====
            if role.key == "radical":
                role_block += """
【强制行为 - 激进者】
- 你必须在每轮发言中提出 **至少 3 个颠覆性观点**。
- 格式：用「颠覆性观点 1/2/3」明确标出。"""
            elif role.key == "conservative":
                role_block += """
【强制行为 - 保守者】
- 你必须在每轮发言中列出 **至少 3 个风险点**。
- 格式：用「风险清单 1/2/3」明确标出。"""
            elif role.key == "judge":
                role_block += """
【强制行为 - 大法官】
- 你必须在裁决中**引用至少 2 个晶体 ID 或孔洞 ID**。
- 格式：「依据 [C012]，判定......」
- 必须输出 `system_basis` 字段。"""
            elif role.key == "spokesperson":
                role_block += """
【强制行为 - 首席发言人】
- 结论先行，不超过 3 条核心信息。
- 禁止使用"可能""或许"等模糊词。"""

            if role.key == "lark":
                role_block += """
【特别角色：百灵鸟】
- 每轮发言必须引用至少 1 条外部信源（格式：[arxiv]、[news]、[hf]、[external]）。
- 说明该信源挑战或补充了哪个默认判断。"""

            if external_brief and len(external_brief) > 20:
                role_block += f"""
【该角色专属外部扫描简报】
{external_brief}"""

            # ===== 轮次动态尾部：变化内容全部后置 =====
            dynamic_tail = ""
            if round_num >= 1:
                ideology = self._get_role_ideology(role.key)
                if ideology:
                    if round_num == 1:
                        # 第2轮：注入完整摘要
                        dynamic_tail += f"""

【角色方法论 · 思想钢印（完整版）】
{ideology}"""
                    else:
                        # 第3轮及以后：仅注入锚点词
                        anchor = self._extract_ideology_anchor(role.key)
                        dynamic_tail += f"""

【角色锚点】{anchor}"""

            if is_reflection:
                dynamic_tail += """

【反思轮次特殊指令】
请回答：你从前几轮学到了什么？新观点与初始观点有何不同？"""

            if arbitration and len(arbitration.strip()) > 0:
                dynamic_tail += f"\n\n【大法官仲裁意见（最高指示）】\n{arbitration.strip()}"

            rumad_focus = getattr(getattr(self, "ctx", None), "rumad_focus", None)
            if rumad_focus and len(rumad_focus) == 2:
                speaker, target = rumad_focus
                dynamic_tail += (
                    f"\n\n【RUMAD 拓扑指令】本轮交锋重点：{target} 必须直接回应 "
                    f"{speaker} 的核心主张，其他角色围绕该交锋补充。"
                )

            return shared_prefix + role_block + dynamic_tail

        except Exception as e:
            self.log(f"⚠️ _role_system 生成失败，使用基础prompt: {e}", "warning")
            return self._fallback_system(role)

    def _fallback_system(self, role: DebateRole) -> str:
        """异常兜底：保持公共前缀 + 角色块结构，避免缓存前缀被兜底文案破坏。"""
        return f"""你是认知晶体树辩论引擎的成员。你的具体角色在下方【角色身份】中定义，必须严格扮演该角色。

辩论元能力：
1. 精准复述对方论点后再回应，禁止稻草人攻击。
2. 区分事实分歧与价值分歧，前者需举证，后者可存异。
3. 当对方证据明显更强时，必须明确承认并吸收。
4. 终极目标不是赢，而是产出融合方案，超越任何单一角色初始输出。

【角色身份】你是认知晶体树辩论引擎中的【{role.name}】。
角色立场：{role.instruction}

请基于你的角色立场进行论述。"""

    def _extract_ideology_anchor(self, role_key: str) -> str:
        """提取角色的锚点词（用于第3轮及以后）"""
        anchors = {
            "radical": "假设全错，颠覆性破局",
            "conservative": "最坏情况，稳健兜底",
            "structural": "同构映射，系统建模",
            "lark": "广博视野，跨界注入",
            "pilgrim": "十年回望，使命锚定",
            "strategist": "机会窗口，借力打力",
            "statesman": "主要矛盾，实事求是",
            "judge": "程序正义，遵循先例",
            "spokesperson": "结论先行，降维翻译",
        }
        return anchors.get(role_key, "")

    # ---- 修改：_independent_round 实现并发调用 ----
    def _independent_round(self, question: str, crystal_context: str, roles: List[DebateRole], baseline_answer: str = "") -> List[Dict]:
        """第一轮独立发言：并发执行所有角色（使用质量参数）"""
        import time
        import concurrent.futures
        
        answers = []
        # ===== 修改：删除字数限制，只保留论述要求 =====
        baseline_note = f"\n\n【参考基线】百灵鸟（裸模型）的初始回答：\n{baseline_answer}\n\n" if baseline_answer else ""

        # 准备每个角色的 prompt 和 system
        role_tasks = []
        for role in roles:
            # ===== 获取该角色的专属外部简报（缓存感知） =====
            role_external = self._get_or_create_role_external(role, question)
            
            # 构造 system 时传入 external_brief
            try:
                system = self._role_system(
                    role, 
                    crystal_context, 
                    is_reflection=False, 
                    external_brief=role_external,
                    round_num=0
                )
            except Exception as e:
                self.log(f"⚠️ 生成 {role.name} 的 system prompt 失败: {e}", "error")
                system = self._fallback_system(role)
            # 构造 prompt（保持不变）
            prompt = f"""用户问题：{question}
{baseline_note}
请基于你的角色立场，给出独立答案。"""
            
            # ===== 新增：把 role, prompt, system 加入 role_tasks =====
            role_tasks.append((role, prompt, system, 2048))

        # 并发执行
        start_time = time.time()
        self.log(f"🚀 启动 {len(role_tasks)} 个角色并发发言...", "system")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(role_tasks)) as executor:
            future_to_role = {}
            for role, prompt, system, exp_words in role_tasks:
                # ===== 直接使用 _call_role_with_retry，不再需要内部函数 =====
                future = executor.submit(self._call_role_with_retry, role, prompt, system, 2, max_tokens=exp_words)
                future_to_role[future] = role
            
            for future in concurrent.futures.as_completed(future_to_role):
                role = future_to_role[future]
                try:
                    result = future.result(timeout=180)
                    self.log(f"✅ {role.name} 发言完成（{count_output_words(result)}字）", "system")
                    answers.append({"role": role.name, "answer": result})
                except concurrent.futures.TimeoutError:
                    self.log(f"❌ {role.name} 执行超时", "error")
                    raise Exception(f"{role.name} 执行超时")
                except Exception as e:
                    self.log(f"❌ {role.name} 发言失败: {e}", "error")
                    raise

        elapsed = time.time() - start_time
        self.log(f"📊 第1轮并发执行完成，耗时 {elapsed:.2f} 秒", "system")

        # 按角色顺序排序
        role_order = {role.key: idx for idx, role in enumerate(roles)}
        answers.sort(key=lambda x: role_order.get(self._map_role_key(x["role"]), 999))
        
        return answers
    
    def _parallel_round0_and_round1(self, question: str, crystal_context: str,
                                     core_roles: List[DebateRole]) -> Tuple[List[Dict], str]:
        import time
        import concurrent.futures

        round1_answers = []
        lark_bare_answer = ""

        complexity = self._estimate_complexity(question)
        if complexity > 0.7:
            min_words, max_words = 1200, 1800
        elif complexity > 0.4:
            min_words, max_words = 1000, 1500
        else:
            min_words, max_words = 800, 1200

        expected_words = (min_words + max_words) // 2

        role_tasks = []
        for role in core_roles:
            prompt = (
                f"用户问题：{question}\n"
                f"请基于你的角色立场给出独立答案，包含结论、理由、证据和风险建议。\n"
                f"**要求：逻辑和论证必须严密，论证完整即可；不设字数目标，禁止为凑字数展开。**"
            )
            system = self._role_system(role, crystal_context)
            role_tasks.append((role, prompt, system, expected_words))

        start_time = time.time()
        total_tasks = len(role_tasks) + 1
        self.log(f"🚀 并发启动 Round 0（百灵鸟裸模型）+ Round 1（{len(role_tasks)} 个角色），共 {total_tasks} 个任务...", "system")

        results = {}

        def execute_role_task(role, prompt, system, max_tokens):
            try:
                return self._call_role_with_retry(role, prompt, system, 2, max_tokens)
            except Exception as e:
                return f"（{role.name} 发言生成失败: {str(e)[:50]}）"

        def execute_lark_bare_task(q):
            try:
                ai_client = AIClient(api_key=self.ai.api_key)
                prompt = f"请直接回答以下问题，给出你最直观、最完整的答案。\n\n问题：{q}"
                raw_answer = ai_client.chat(prompt, system="你是一位知识广博的通用AI，请直接输出完整回答。")

                if raw_answer is None:
                    return "（百灵鸟裸模型生成失败: 返回为空）"
                if not isinstance(raw_answer, str):
                    return f"（百灵鸟裸模型生成失败: 类型异常 {type(raw_answer)}）"
                if raw_answer.startswith("错误") or raw_answer.startswith("AI调用失败"):
                    return f"（百灵鸟裸模型生成失败: {raw_answer[:50]}）"

                if count_output_words(raw_answer) < 400:
                    expand = ai_client.chat(
                        f"请将以下回答扩展为更详细的论述（至少800字）：\n{raw_answer}",
                        system="请只输出扩展后的正文。"
                    )
                    if expand and isinstance(expand, str) and len(expand) > len(raw_answer):
                        return expand
                    return raw_answer
                return raw_answer
            except Exception as e:
                return f"（百灵鸟裸模型生成失败: {str(e)[:50]}）"

        with concurrent.futures.ThreadPoolExecutor(max_workers=total_tasks) as executor:
            future_to_key = {}

            for idx, (role, prompt, system, exp_words) in enumerate(role_tasks):
                key = f"role_{idx}"
                future = executor.submit(execute_role_task, role, prompt, system, exp_words)
                future_to_key[future] = (key, role)

            future = executor.submit(execute_lark_bare_task, question)
            future_to_key[future] = ("lark_bare", None)

            for future in concurrent.futures.as_completed(future_to_key):
                key, role = future_to_key[future]
                try:
                    result = future.result(timeout=180)
                    if key == "lark_bare":
                        lark_bare_answer = result
                        self.log("✅ 百灵鸟裸模型完成", "system")
                    else:
                        results[key] = {"role": role.name, "answer": result}
                        self.log(f"✅ {role.name} 发言完成", "system")
                except concurrent.futures.TimeoutError:
                    self.log(f"❌ {key} 执行超时", "error")
                    if key == "lark_bare":
                        lark_bare_answer = "（百灵鸟裸模型生成超时）"
                    else:
                        results[key] = {"role": role.name, "answer": f"（{role.name} 执行超时）"}
                except Exception as e:
                    error_msg = str(e)
                    if key == "lark_bare":
                        self.log(f"❌ 百灵鸟裸模型失败: {error_msg}", "error")
                        lark_bare_answer = "（百灵鸟裸模型生成失败）"
                    else:
                        self.log(f"❌ {role.name} 发言失败: {error_msg}", "error")
                        results[key] = {"role": role.name, "answer": f"（{role.name} 发言失败: {error_msg[:50]}）"}

        for idx, (role, _, _, _) in enumerate(role_tasks):
            key = f"role_{idx}"
            if key in results:
                round1_answers.append(results[key])
            else:
                self.log(f"⚠️ {role.name} 的结果丢失", "warning")
                round1_answers.append({"role": role.name, "answer": f"（{role.name} 结果丢失）"})

        elapsed = time.time() - start_time
        self.log(f"📊 Round 0 + Round 1 并发执行完成，耗时 {elapsed:.2f} 秒", "system")

        return round1_answers, lark_bare_answer
    
    # ---- 修改：_debate_round 实现并发调用 ----
    def _debate_round(self, question, crystal_context, previous, audit, round_no, roles,
                      lark_answer=None, arbitration: str = ""):
        """后续辩论轮：并发执行所有角色（使用质量参数）"""
        import time
        import concurrent.futures
        
        answers = []

        # ===== 历史分层：更早轮次只留 300 字摘要，最近一轮保留全文 =====
        summary_lines = []
        if round_no >= 3 and hasattr(self, "ctx"):
            for round_idx in range(1, round_no):
                summary = self.ctx.round_summaries.get(round_idx, "")
                if summary:
                    summary_lines.append(f"### 第{round_idx}轮摘要\n{summary}")

        previous_text = "\n\n".join([f"### {item['role']}\n{item['answer']}" for item in previous])
        if lark_answer and not any(item["role"] == "百灵鸟" for item in previous):
            previous_text = f"### 百灵鸟（外部知识）\n{lark_answer['answer']}\n\n" + previous_text

        # ===== 最近一轮全文超长时压缩：目标 12k-15k 字，每角色 1.5k-1.9k 字 =====
        if len(previous_text) > ROUND_HISTORY_MAX_CHARS and previous:
            per_role = max(
                ROUND_HISTORY_PER_ROLE_MIN,
                min(
                    ROUND_HISTORY_PER_ROLE_MAX,
                    ROUND_HISTORY_MAX_CHARS // len(previous),
                ),
            )
            compressed_items = []
            for item in previous:
                answer = item.get("answer", "")
                if len(answer) > per_role:
                    answer = summarize_role_answer(answer, per_role)
                compressed_items.append({"role": item["role"], "answer": answer})
            previous_text = "\n\n".join(
                [f"### {item['role']}\n{item['answer']}" for item in compressed_items]
            )
            if lark_answer and not any(item["role"] == "百灵鸟" for item in compressed_items):
                lark_compressed = lark_answer["answer"]
                if len(lark_compressed) > per_role:
                    lark_compressed = summarize_role_answer(lark_compressed, per_role)
                previous_text = f"### 百灵鸟（外部知识）\n{lark_compressed}\n\n" + previous_text
            self.log(
                f"🧩 [历史压缩] 第 {round_no} 轮最近一轮全文超过 "
                f"{ROUND_HISTORY_MAX_CHARS} 字，压缩到约 {len(previous_text)} 字"
                f"（每角色约 {per_role} 字）",
                "system",
            )

        if summary_lines:
            previous_text = (
                "\n\n".join(summary_lines)
                + "\n\n【最近一轮完整观点】\n"
                + previous_text
            )

        # 准备每个角色的任务
        role_tasks = []
        arbitration_block = f"\n\n【大法官仲裁意见（最高指示）】\n{arbitration}" if arbitration else ""
        for role in roles:
            # ===== 新增：获取该角色的专属外部简报（缓存复用） =====
            role_external = self._get_or_create_role_external(role, question)
            
            feedback = (audit.get("feedback_by_role") or {}).get(role.name, "")
            other_names = [item["role"] for item in previous if item["role"] != role.name]
            if lark_answer and "百灵鸟" not in other_names:
                other_names.append("百灵鸟")
            target_lines = "\n".join([f"对 {target}：[精准复述其具体论据后，给出反驳理由]" for target in other_names[:3]])

            prompt = f"""用户问题：{question}{arbitration_block}

上一轮各方观点：
{previous_text}

逻辑检查员给你的反馈：
{feedback}

请输出以下结构：
【靶向攻击】
{target_lines}

【辩护与吸收】
[我坚持的核心理由是……]
[我从X角色处吸收了……因为其证据充分/逻辑严密]

【终选与裁决】在各方观点中，选择唯一最符合事实与逻辑的一条路径作为结论，并明确给出三条驳回其他路径的硬核理由（基于事实/逻辑/证据缺失）。

            **只要求逻辑和论证严密，论证完整即可；不设字数目标，禁止为凑字数展开。字数上不封顶下不保底，但必须逻辑闭环。**
"""
            # ===== 修改：_role_system 调用增加 external_brief 参数 =====
            # ===== 修改：_role_system 调用增加 external_brief 参数 =====
            try:
                system = self._role_system(
                    role, crystal_context, is_reflection=False,
                    external_brief=role_external, round_num=round_no, arbitration=arbitration
                )
            except Exception as e:
                self.log(f"⚠️ 生成 {role.name} 的 system prompt 失败: {e}", "error")
                # 兜底：确保 system 有值
                system = self._fallback_system(role)

            role_tasks.append((role, prompt, system, 2048))

        # 并发执行
        start_time = time.time()
        self.log(f"🚀 启动第 {round_no} 轮 {len(role_tasks)} 个角色并发发言...", "system")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(role_tasks)) as executor:
            future_to_role = {}
            for role, prompt, system, exp_words in role_tasks:
                # ===== 直接使用 _call_role_with_retry，不再需要内部函数 =====
                future = executor.submit(self._call_role_with_retry, role, prompt, system, 2, max_tokens=exp_words)
                future_to_role[future] = role
            
            for future in concurrent.futures.as_completed(future_to_role):
                role = future_to_role[future]
                try:
                    result = future.result(timeout=180)
                    self.log(f"✅ {role.name} 第 {round_no} 轮发言完成（{count_output_words(result)}字）", "system")
                    answers.append({"role": role.name, "answer": result})
                except concurrent.futures.TimeoutError:
                    self.log(f"❌ {role.name} 第 {round_no} 轮执行超时", "error")
                    raise Exception(f"{role.name} 执行超时")
                except Exception as e:
                    self.log(f"❌ {role.name} 第 {round_no} 轮发言失败: {e}", "error")
                    raise

        elapsed = time.time() - start_time
        self.log(f"📊 第 {round_no} 轮并发执行完成，耗时 {elapsed:.2f} 秒", "system")

        # 按角色顺序排序
        role_order = {role.key: idx for idx, role in enumerate(roles)}
        answers.sort(key=lambda x: role_order.get(self._map_role_key(x["role"]), 999))
        return answers

    def _reflection_round(self, question, crystal_context, previous_answers, audit, roles, round_num,
                          arbitration: str = ""):
        """反思轮：并发执行所有角色（使用质量参数）"""
        import time
        import concurrent.futures
        
        answers = []
        role_tasks = []  # ===== 新增：需要初始化 role_tasks =====
        arbitration_block = f"\n\n【大法官仲裁意见（最高指示）】\n{arbitration}" if arbitration else ""
        # ===== 修改：删除字数限制 =====
        for role in roles:
            # ===== 新增：获取该角色的专属外部简报（缓存复用） =====
            role_external = self._get_or_create_role_external(role, question)
            
            feedback = (audit.get("feedback_by_role") or {}).get(role.name, "")
            own_previous = next(
                (item["answer"] for item in previous_answers if item.get("role") == role.name),
                "",
            )
            summary = ""
            if hasattr(self, "ctx"):
                summary = self.ctx.round_summaries.get(round_num, "") or self.ctx.round_summaries.get(round_num - 1, "")
            if summary or own_previous:
                previous_text = (
                    f"【第 {round_num} 轮摘要】\n{summary}\n\n"
                    f"【你上一轮发言】\n{own_previous}"
                )
            else:
                previous_text = "\n\n".join(
                    [f"【{item['role']}】\n{item['answer']}" for item in previous_answers]
                )
            prompt = f"""用户问题：{question}{arbitration_block}

你刚刚完成了第 {round_num} 轮辩论。

【第 {round_num} 轮记录】
{previous_text}

【审计员反馈】{feedback}

现在进入「反思」阶段 —— 请回答：
1. 你从本轮中（尤其是从百灵鸟的外部知识）学到了什么之前不知道的信息？
2. 基于这些新信息，你之前的立场需要做哪些**具体的修正**？（至少 3 点）
3. 修正后，你的**新立场**是什么？

**输出要求**：输出「反思声明」**严禁凑字数**，用最精炼的语言写出你的反思，聚焦于变化和增量。
"""
            # ===== 修改：_role_system 调用增加 external_brief 参数 =====
            try:
                system = self._role_system(
                    role, 
                    crystal_context, 
                    is_reflection=True, 
                    external_brief=role_external,
                    round_num=round_num,
                    arbitration=arbitration
                )
            except Exception as e:
                self.log(f"⚠️ 生成 {role.name} 的 system prompt 失败: {e}", "error")
                system = self._fallback_system(role)
            role_tasks.append((role, prompt, system, 2048))

        # 并发执行
        start_time = time.time()
        self.log(f"🚀 启动第 {round_num} 轮反思（{len(roles)} 个角色并发）...", "system")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(role_tasks)) as executor:
            future_to_role = {}
            for role, prompt, system, exp_words in role_tasks:
                # ===== 直接使用 _call_role_with_retry，不再需要内部函数 =====
                future = executor.submit(self._call_role_with_retry, role, prompt, system, 2, max_tokens=exp_words)
                future_to_role[future] = role
            
            for future in concurrent.futures.as_completed(future_to_role):
                role = future_to_role[future]
                try:
                    result = future.result(timeout=180)
                    self.log(f"✅ {role.name} 反思完成（{count_output_words(result)}字）", "system")
                    answers.append({"role": role.name, "answer": result})
                except concurrent.futures.TimeoutError:
                    self.log(f"❌ {role.name} 反思超时", "error")
                    raise Exception(f"{role.name} 反思超时")
                except Exception as e:
                    self.log(f"❌ {role.name} 反思失败: {e}", "error")
                    raise

        elapsed = time.time() - start_time
        self.log(f"📊 第 {round_num} 轮反思并发执行完成，耗时 {elapsed:.2f} 秒", "system")
        
        return answers

    def _check_convergence(self, debate_answers, reflection_answers):
        all_texts = [item["answer"] for item in debate_answers] + [item["answer"] for item in reflection_answers]
        if len(all_texts) < 3:
            return False
        import itertools
        sims = [self._jaccard(a, b) for a, b in itertools.combinations(all_texts, 2)]
        avg_sim = sum(sims) / len(sims) if sims else 0
        self.log(f"📊 当前观点收敛度：{avg_sim:.2f}", "system")
        return avg_sim > float(Config.CONVERGENCE_CONFIG["jaccard_convergence_threshold"])

    def _maybe_early_judge(self, question: str, rounds: List[Dict], orchestrator, round_no: int) -> None:
        """连续两轮 major_conflict 时，在下一轮开始前调用大法官生成仲裁意见。"""
        if self.ctx.judge_early_called or self.ctx.conflict_streak < 2:
            return
        try:
            atomic = orchestrator._extract_atomic(question, rounds)
            judge_result = orchestrator._run_judge(question, atomic)
            verdict = (judge_result.get("final_verdict") or "").strip()
            if verdict:
                self.ctx.arbitration = verdict
                self.ctx.arbitration_round = round_no
                self.ctx.judge_early_called = True
                self.ctx.conflict_streak = 0
                self.log(f"⚖️ 大法官提前介入（第{round_no}轮前）仲裁意见已生成：{verdict[:60]}...", "system")
            else:
                self.log("⚠️ 大法官提前介入未生成有效仲裁意见，继续原流程", "warning")
        except Exception as e:
            self.log(f"⚠️ 大法官提前介入失败：{e}", "warning")

    def _diagnose_gaps(self, question: str, audit: Dict, rounds: List[Dict]) -> Dict[str, Any]:
        """检测本轮辩论的决策/证据/情境三类缺口。"""
        all_text = " ".join(
            ans.get("answer", "")
            for rd in rounds
            for ans in rd.get("answers", [])
        )
        gaps = []
        if not re.search(r'备选|替代|方案B|备选方案|Plan\s*B|plan\s*b', all_text):
            gaps.append({"type": "decision", "label": "决策缺口", "desc": "辩论中没有人讨论备选方案"})
        refs = len(re.findall(r'\[C\d+\]|\[H\d+\]', all_text))
        if refs < 3:
            gaps.append({"type": "evidence", "label": "证据缺口", "desc": "关键论点没有引用足够的晶体/外部证据"})
        if not re.search(r'政策|法规|市场|监管|趋势|外部|经济|需求变化', all_text):
            gaps.append({"type": "context", "label": "情境缺口", "desc": "辩论没有考虑外部环境变化（如政策、市场）"})
        return {"gaps": gaps[:3], "options": [g["label"] for g in gaps[:3]]}

    # ===== 在这里添加 _audit 方法 =====
    def _audit(self, question, answers, round_no):
        # ----- 获取系统信号 -----
        audit_rules = load_audit_rules()
        audit_max_chars = int(audit_rules.get("audit_role_max_chars", 1000))
        min_feedback_chars = int(audit_rules.get("role_feedback_min_chars", 200))
        section_min_chars = int(audit_rules.get("role_feedback_section_min_chars", 30))
        expand_chars = int(audit_rules.get("role_feedback_expand_chars", 150))
        max_retries = int(audit_rules.get("audit_max_retries", 2))
        summary_min_chars = int(audit_rules.get("round_summary_min_chars", 50))
        summary_max_chars = int(audit_rules.get("round_summary_max_chars", 300))

        state = self.engine.load_layer_state()
        layers = state.get("layers", {})
        l1_capacity = sum(1 for layer in layers.values() if layer == "L1")
        holes = self.engine.parse_holes()
        high_urgency_holes = [h.id for h in holes if h.urgency >= 0.7]
        health_score = 5.0
        try:
            audit_status = self.engine.get_audit_status()
            if audit_status.get("available"):
                health_score = audit_status.get("health_score", 5.0)
        except:
            pass

        audit_items = []
        compressed_count = 0
        for item in answers:
            answer = item.get("answer", "")
            if len(answer) > audit_max_chars:
                try:
                    answer = summarize_role_answer(answer, audit_max_chars)
                    compressed_count += 1
                except Exception:
                    pass
            audit_items.append({"role": item.get("role", "未知"), "answer": answer})
        if compressed_count:
            self.log(f"🧩 [审计输入压缩] {compressed_count}/{len(audit_items)} 个角色发言已压缩", "system")
        answers_text = "\n\n".join(
            [f"### {item['role']}\n{item['answer']}" for item in audit_items]
        )

        prompt = f"""你是认知晶体树中的【审计员】。你的任务是针对本轮辩论，为每个角色提供**详细、具体、可执行的改进建议**。

【强制输出格式】你必须为每个角色输出以下三个部分，缺一不可：
1. **薄弱环节**：该角色论证中最脆弱的部分（引用其原文片段，至少 20 字）。
2. **关键分歧点**：该角色与其他角色在事实或逻辑上的核心冲突（至少 {section_min_chars} 字）。
3. **补强方向**：该角色下一轮应该补充什么证据或逻辑（至少 {section_min_chars} 字）。
【长度约束】每个角色的总反馈必须 ≥ {min_feedback_chars} 字。

【系统背景信号】（必须纳入考量）
- L1 晶体容量：{l1_capacity} / {Config.L1_MAX}（已满时，建议不要引入颠覆性新概念）
- 当前孔洞数：{len(holes)} 条（高紧迫度孔洞：{high_urgency_holes}）
- 当前健康评分：{health_score}/10（低分时建议优先修复证据链）

【辩论记录】
{answers_text}

请返回 JSON（严格按以下 schema）：
{{
  "feedback_by_role": {{
    "激进者": "【薄弱环节】...\n【关键分歧点】...\n【补强方向】...",
    "保守者": "...",
    ...
  }},
  "disagreement_map": {{
    "fact": [],
    "logic": [],
    "risk_preference": [],
    "value": [],
    "term": []
  }},
  "major_conflict": false,
  "evidence_scores": {{"激进者": 0.8, ...}},
  "should_stop": false,
  "summary": "100字内的审计摘要",
  "round_summary": "300字内的本轮摘要（必须包含核心分歧、关键冲突、质量判断）"
}}

【特别提醒】如果某个角色的反馈不足 200 字，你会被要求重写。请一次性提供完整反馈。"""

        external_context = getattr(self.ctx, "audit_external_context", "") or ""
        if external_context and len(external_context) > 20:
            prompt += f"""

【外部知识参考（审计判断依据）】
{external_context}"""

        raw_audit = self.ai.chat_json(prompt, temperature=0.3)

        # ===== 字数验证与重试 =====
        for retry_count in range(max_retries + 1):
            feedbacks = raw_audit.get("feedback_by_role", {})
            short_feedbacks = {}
            for role, feedback_text in feedbacks.items():
                output_words = count_output_words(feedback_text)
                if output_words < min_feedback_chars:
                    short_feedbacks[role] = output_words

            if not short_feedbacks:
                break

            if retry_count >= max_retries:
                for role, length in short_feedbacks.items():
                    raw_audit["feedback_by_role"][role] += (
                        f"\n\n【补强追加】上述反馈不足{min_feedback_chars}字（当前{length}字）。"
                        f"审计员建议重点解决'薄弱环节'中指出的问题。"
                    )
                self.log("⚠️ 审计反馈字数不足，已追加补强文本", "warning")
                break

            self.log(f"🔄 审计反馈字数不足，重试 {retry_count+1}/{max_retries} 次 | 短反馈角色: {', '.join(short_feedbacks.keys())}", "system")

            expand_prompt = f"""审计员：你之前对以下角色的反馈字数不足 {min_feedback_chars} 字：
{chr(10).join([f"- {role}：当前 {length} 字" for role, length in short_feedbacks.items()])}
请针对这些角色，**补充**不少于 {expand_chars} 字的详细分析（不要重复已有内容）。
格式：严格按"薄弱环节/关键分歧点/补强方向"三部分展开。
只输出 JSON 字典，键为角色名，值为补充文本。"""
            try:
                expansion = self.ai.chat_json(expand_prompt, temperature=0.3)
                if "error" not in expansion:
                    for role, extra_text in expansion.items():
                        if role in raw_audit["feedback_by_role"]:
                            raw_audit["feedback_by_role"][role] += f"\n\n【补强追加】\n{extra_text}"
            except Exception as e:
                self.log(f"⚠️ 审计补强失败: {e}", "warning")

        # 存储轮次摘要（供历史压缩使用）
        round_summary = raw_audit.get("round_summary", "")
        if round_summary and len(round_summary) > summary_min_chars:
            self.ctx.round_summaries[round_no] = round_summary[:summary_max_chars]
            self.log(f"🧩 [摘要写入] 第 {round_no} 轮摘要已存储 ({len(round_summary)} 字)", "system")
        else:
            fallback_summary = self._build_fallback_round_summary(answers)
            self.ctx.round_summaries[round_no] = fallback_summary[:summary_max_chars]
            self.log(
                f"⚠️ [摘要写入] 第 {round_no} 轮审计摘要为空或过短，"
                f"已用角色回答兜底 ({len(fallback_summary)} 字)",
                "warning",
            )

        return raw_audit

    def _build_fallback_round_summary(self, answers: List[Dict]) -> str:
        """审计摘要缺失时，用本轮角色回答的首句生成确定性兜底摘要。"""
        parts = []
        for item in answers or []:
            role = item.get("role", "未知")
            answer = item.get("answer", "") or ""
            first_sentence = re.split(r"[。！？!?；;\n]", answer.strip())[0][:80] if answer.strip() else "（无回答）"
            parts.append(f"{role}：{first_sentence}")
        return "；".join(parts)


    def get_roles_with_twin(self, include_twin: bool = True, fingerprint=None) -> List[DebateRole]:
        """
        获取辩论角色列表（可选择是否包含替身角色）
        """
        if not include_twin:
            return self.roles

        # 获取核心角色（激进者、保守者、结构主义者）
        core = self._core_roles()

        # 生成替身角色
        twin = self.generate_twin_role(fingerprint)

        # 用替身替换执行者或审计者（保留三个核心角色 + 替身）
        # 替换最后一个角色（通常是审计者或执行者）
        if len(core) >= 3:
            # 保留前两个核心角色，第三个替换为替身
            # 但实际上激进者、保守者、结构主义者都很重要
            # 更好的方式：在原有角色基础上增加替身
            result = core[:]  # 复制核心角色
            # 如果已经有 5 个角色，替换最后一个
            if len(self.roles) > 3:
                # 保留所有角色，替身作为额外角色加入（但要注意注意力上限）
                result = self.roles[:] + [twin]
            else:
                result = self.roles[:] + [twin]
            return result

        return self.roles + [twin]

    # ---- run 方法保持不变（内部调用已修改） ----
    def run(self, question: str, mode: str = "debate_full",
            max_rounds: int = int(Config.CONVERGENCE_CONFIG["default_max_rounds"])) -> Dict:
    
        """
        多角色辩论主流程 —— 认知五棱镜流水线

        [用户输入问题]
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 0：预处理与路由（CheapGate + 指纹加载）                         │
        │   - 便宜门判定复杂度 → 简单问题直接拦截（0次LLM调用）                │
        │   - 加载认知指纹 → 注入替身/认知风格                                 │
        │   - 问题分类 → 决定检索策略（技术/人文/通用）                        │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 1：晶体缓存与基线（只检索一次）                                 │
        │   - 检查 DebateContext.crystal_cache                                 │
        │   - 若未命中：检索 L1/L2 晶体，存入缓存                              │
        │   - 百灵鸟裸模型（Round 0）→ 生成 baseline_answer                    │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 2：多棱镜外部知识注入（全员专属简报）                           │
        │   FOR EACH 角色：                                                     │
        │     - 根据角色立场生成 3~5 个搜索意图                                │
        │     - 获取/合成该角色专属外部简报                                    │
        │     - 存入 DebateContext.role_external_cache（全轮次复用）            │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 3：辩论循环（Stage 1 → Stage 3）                               │
        │   Round 1（核心三人组）：                                            │
        │     输入：问题 + baseline + 晶体缓存 + 各角色专属简报               │
        │     输出：激进/保守/结构 三份独立立场                                │
        │                                                                      │
        │   Round 2（全员七人）：                                              │
        │     输入：Round 1 答案 + 审计反馈 + 各角色专属简报（缓存）          │
        │     输出：七份对抗性辩论答案                                         │
        │                                                                      │
        │   Round 3..N（循环）：                                               │
        │     输入：上一轮答案 + 审计反馈 + 收敛判断                          │
        │     输出：迭代辩论答案                                               │
        │                                                                      │
        │   ★ 收敛判断：若 Jaccard > 0.50，提前退出                           │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 4：反思轮（全员修正立场）                                       │
        │   - 输入：最后一轮辩论答案 + 审计反馈                                │
        │   - 每个角色输出"修正声明"：学到了什么、立场如何修正                │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 5：大法官终审裁决                                               │
        │   - 输入：全部轮次答案 + 晶体卡片 + 核心操作原则                    │
        │   - 输出 1：绩效看板（7项KPI × 9角色，贡献度%）                     │
        │   - 输出 2：终审裁决（明确采纳/附条件/暂缓/驳回）                   │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 6：首席发言人初稿（5个原始版本）                                │
        │   - 输入：大法官裁决 + 各角色核心观点                                │
        │   - 输出 5 份原始报告：                                               │
        │     ① 老板版（决策摘要）                                             │
        │     ② 员工版（SOP操作手册）                                         │
        │     ③ 新人版（通俗解释）                                             │
        │     ④ 专家版（含评分矩阵、审计综述）                                │
        │     ⑤ 儒雅笔谈（文人风格附录）                                      │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │ 阶段 7：终稿润色师（评测友好型交付）                                 │
        │   - 输入：5份原始报告                                                │
        │   - 动作：压缩冗余、删除强行关联、精炼语言                          │
        │   - 输出 5份润色版报告（信息密度翻倍，评测得分+9分）                │
        └───────────────────────────────────────────────────────────────────────┘
            │
            ▼
        [最终交付：5个版本 + 原始辩论日志 + 元数据]

        这段注释完整描述了系统的数据流和控制逻辑，是"认知五棱镜"的官方实现蓝本。
        """
           
        """
        运行辩论 - 由 OutputOrchestrator 输出结构化数据
        """
        # ===== 确保 self 是 DebateEngine 实例 =====
        if not isinstance(self, DebateEngine):
            raise TypeError(f"run() 被非 DebateEngine 对象调用: {type(self)}")
        # ===== Day 2 强制隔离上下文（必须第一行执行） =====
        if not hasattr(self, 'ctx') or self.ctx is None:
            self.ctx = DebateContext()
        self.ctx.current_question = question
        corrected_question, correction_message = self.engine.cheap_gate._sanitize_user_input(question)
        if correction_message:
            self.log(correction_message, "warning")
            question = corrected_question
            self.ctx.current_question = question
        self.ctx.start_time = time.time()
        self.ctx.routing_result = {}
        self.ctx.current_classification = {}
        self.ctx.cognitive_operators = "[思维模式：平衡]"
        self.ctx.history_result = {}
        self.ctx.reused_crystals = []          # ← 关键：移到这里
        self.ctx.forced_perspective = ""
        self.ctx.external_has_new = False
        self.ctx.token_count = 0
        self.ctx.role_external_cache = {}
        self.ctx.audit_external_context = ""
        self.ctx.last_round_answers = []

        if len(self.roles) < 3:
            raise ValueError("辩论至少需要 3 个角色")

        max_rounds = max(3, min(8, int(max_rounds or 4)))
        self._emit_progress("初始化", 0)

        # ===== Day 0: 运行时自检断言 =====
        self._run_day0_runtime_assertions()

        # ===== 便宜门路由 =====
        routing_result = self.engine.cheap_gate.check(question, [])
        self.ctx.routing_result = routing_result
        self.log(f"[STAGE 0] 预处理与路由完成 | 复杂度={routing_result.get('complexity')} | 跳过LLM={routing_result.get('skip_llm')}", "system")
        # ... 后续代码保持不变

        # ===== H9 补丁：便宜门拦截简单问题，跳过 LLM 调用 =====
        # 确保 routing_result 已定义
        try:
            _routing = routing_result
        except NameError:
            _routing = self.engine.cheap_gate.check(question, [])
            self.ctx.routing_result = _routing
            self._routing_result = _routing
        
        if _routing.get("skip_llm", False):
            self.log(f"⚡ 便宜门触发（{_routing.get('complexity', 'simple')}）：跳过 LLM，直接回复规则引擎结果", "system")
            mock_answer = _routing.get("reason", "已收到您的消息。如需深度分析，请提出更具体、复杂的问题。")
            
            # 构造最小兼容返回结构，防止 GUI / API 解析失败
            return {
                "mode": mode,
                "question": question,
                "rounds": [],
                "board_version": mock_answer,
                "employee_version": "无需操作",
                "novice_version": mock_answer,
                "expert_version": "规则引擎处理（简单问题）",
                "elegant_epilogue": "",
                "judge_audit": {
                    "summary": f"便宜门拦截：{_routing.get('reason', '')}",
                    "role_scorecard": []
                },
                "final_schema": {
                    "board_version": mock_answer,
                    "employee_version": "无需操作",
                    "novice_version": mock_answer,
                    "expert_version": "规则引擎处理",
                    "elegant_epilogue": "",
                    "judge_audit": {"summary": "规则引擎", "role_scorecard": []}
                },
                "_meta": {"routing": _routing, "skipped_llm": True}
            }

        # ===== Day 2.8: 元问题分类器 =====
        if self.question_classifier:
            try:
                classification = self.question_classifier.classify(question)
                self._current_classification = classification
                label = classification.get('label', '未知')
                pipeline = classification.get('pipeline', '通用')
                self.log(f"🔍 当前问题被分类为：{label}，走{pipeline}路径", "system")
            except Exception as e:
                self.log(f"⚠️ 元问题分类失败：{e}，使用默认路径", "warning")
                self._current_classification = {"label": "通用", "type": "general", "pipeline": "通用"}
        else:
            self._current_classification = {"label": "通用", "type": "general", "pipeline": "通用"}

        # ===== Day 2.5: 认知风格注入 =====
        try:
            fingerprint = self.engine.fingerprint_extractor.get_fingerprint()
            operators = self.engine.fingerprint_extractor.get_cognitive_operators(fingerprint)
            self.ctx.cognitive_operators = operators
            self.log(f"🧠 注入认知风格：{operators}", "system")
        except Exception as e:
            self.log(f"⚠️ 认知风格注入失败：{e}，使用默认认知风格继续", "warning")
            self._cognitive_operators = "[思维模式：平衡] [论证偏好：平衡] [输出偏好：平衡]"
            self.ctx.cognitive_operators = self._cognitive_operators

        # ===== Day 4: 历史诊断与经验复用 =====
        try:
            history_result = self.engine.meta.diagnose_history(question)
            self.ctx.history_result = history_result
            if history_result.get("matched"):
                self._reused_crystals = history_result.get("crystal_combination", [])
                self.log(f"📚 复用历史经验：匹配历史问题（相似度 {history_result['match_score']:.2f}）："
                         f"{history_result.get('matched_question', '')[:50]}...", "system")
                if self._reused_crystals:
                    self.log(f"   有效晶体组合：{', '.join(self._reused_crystals[:5])}", "system")
            else:
                self.ctx.reused_crystals = []
                self.log(f"📚 未找到匹配历史经验（最高相似度 {history_result.get('match_score', 0):.2f}）", "system")
        except Exception as e:
            self.ctx.reused_crystals = []
            self._history_result = {}
            self.log(f"⚠️ 历史诊断失败：{e}", "warning")

        # ===== Day 0: 埋点计时 =====
        self._start_time = time.time()
        self._token_count = 0
        self._call_log_start = len(AIClient.CALL_LOG)

        # 加载认知风格（用于后续）
        try:
            fingerprint = self.engine.fingerprint_extractor.get_fingerprint()
            operators = self.engine.fingerprint_extractor.get_cognitive_operators(fingerprint)
            self.ctx.cognitive_operators = operators
        except Exception:
            self._cognitive_operators = "[思维模式：平衡] [论证偏好：平衡] [输出偏好：平衡]"

        # ===== Day 1 & 4: 警报检查内部函数（含失败轨迹记录） =====
        def _check_alarms_for_round(round_answers, round_no, audit):
            """检查本轮指标并触发警报，同时记录失败轨迹"""
            self.ctx.last_round_answers = round_answers
            # 计算 Jaccard
            jaccard = self._average_jaccard([item["answer"] for item in round_answers])
            # 晶体引用率：计算有引用的回答占比（而非平均引用数）
            total_answers = len(round_answers)
            # 统计有多少个回答至少包含一个晶体引用
            ref_count_answers = 0
            total_refs = 0
            for item in round_answers:
                answer = item.get("answer", "")
                crystal_matches = len(re.findall(r'\[C\d+\]', answer))
                hole_matches = len(re.findall(r'\[H\d+\]', answer))
                refs_in_answer = crystal_matches + hole_matches
                total_refs += refs_in_answer
                if refs_in_answer > 0:
                    ref_count_answers += 1
            # 引用率 = 有引用的回答数 / 总回答数（0-1 之间的百分比）
            ref_rate = ref_count_answers / max(1, total_answers)
            self.log(f"第{round_no}轮警报检查 | 答案数={total_answers} | "
                     f"有引用回答数={ref_count_answers} | 总引用数={total_refs} | 引用率={ref_rate:.2f}", "debug")
            
            bias_amp = compute_bias_amplification(round_answers)
            evidence_count = 0
            absolute_count = 0
            contradiction_count = 0
            sentence_count = 0
            reliable_count = 0
            for item in round_answers:
                answer = item.get("answer", "") or ""
                if re.search(r'\[(arxiv|news|hf|external)\]|https?://|证据|依据|数据来源', answer):
                    evidence_count += 1
                contradiction_count += sum(answer.count(m) for m in ("矛盾", "冲突", "前后不一", "互相否定", "自相矛盾"))
                absolute_count += sum(answer.count(w) for w in ("必然", "一定", "绝对", "唯一", "所有", "全部", "必定"))
                sentence_count += max(1, len(re.findall(r'[。！？!?]', answer)) + 1)
                if _is_reliable_output(answer):
                    reliable_count += 1
            evidence_strength = evidence_count / max(1, total_answers)
            logic_consistency = 1 - min(1.0, contradiction_count / max(1, total_answers))
            overreach_score = min(1.0, absolute_count / max(1, sentence_count))
            reliability_score = reliable_count / max(1, total_answers)
            metrics = {
                "crystal_reference_rate": ref_rate,
                "bias_amplification": bias_amp,
                "external_has_new": self._external_has_new,
                "jaccard_similarity": jaccard,
                "evidence_strength": evidence_strength,
                "logic_consistency": logic_consistency,
                "overreach_score": overreach_score,
                "reliability_score": reliability_score,
            }
            triggered = self.alarm_monitor.check(metrics)
            self.log(f"触发警报数={len(triggered)}", "debug")

            for alarm in triggered:
                # Day 4: 记录失败轨迹
                if alarm["rule"] == "knowledge_poverty":
                    self._record_failure_trace(
                        self.ctx.current_question or question,
                        "low_crystal_reference",
                        {
                            "ref_rate": ref_rate,
                            "threshold": 0.5,
                            "round": round_no,
                            "effective_crystals": getattr(self, '_reused_crystals', [])
                        }
                    )
                elif alarm["rule"] == "thought_stagnation":
                    self._record_failure_trace(
                        self.ctx.current_question or question,
                        "debate_diverged",
                        {
                            "jaccard": jaccard,
                            "threshold": 0.8,
                            "round": round_no
                        }
                    )
                # 记录进化事件
                self.engine.log_evolution_event(
                    "alarm",
                    {
                        "rule": alarm["rule"],
                        "message": alarm["message"],
                        "action": alarm["action"],
                        "data": alarm.get("data", {}),
                        "round": round_no,
                        "trigger": "alarm"
                    }
                )
                # 处理警报
                self.alarm_monitor.handle_alarm(alarm, self)
            self._external_has_new = False
            return triggered
        
        core_roles = self._core_roles()
        priority_names = [r.name for r in core_roles if self.rumad.user_preferences.get(r.name, 0.0) > 0]
        if priority_names:
            self.log(f"🧠 票选优先调用角色：{priority_names}", "system")
        lark = next((r for r in self.roles if r.key == "lark"), None)
        all_roles = core_roles + [lark] if lark else core_roles

        # ===== 动态路由 =====
        routing_result = self.engine.cheap_gate.check(question, [])
        complexity = routing_result.get("complexity", "high")
        self.ctx.routing_result = routing_result

        if complexity == "simple":
            # 简单问题只激活 3 个核心角色
            core_keys = ["radical", "conservative", "structural"]
            all_roles = [r for r in all_roles if r.key in core_keys]
            self.log(f"🚀 动态路由：简单问题，激活 {len(all_roles)} 个角色（激进者+保守者+结构主义者）", "system")
        elif complexity == "medium":
            # 中等问题激活 5 个角色（核心 + 执行者 + 审计者）
            core_keys = ["radical", "conservative", "structural", "executor", "auditor"]
            all_roles = [r for r in all_roles if r.key in core_keys]
            self.log(f"🚀 动态路由：中等复杂度，激活 {len(all_roles)} 个角色", "system")
        else:
            self.log(f"🚀 动态路由：高复杂度，全量激活 {len(all_roles)} 个角色", "system")
        
        # ===== Round 0 + Round 1：并发执行百灵鸟裸模型 + 核心角色 =====
        self._emit_progress("Round 0 + Round 1 并发启动", 10)
        # ===== 晶体缓存复用（只检索一次） =====
        if not self.ctx.is_crystal_cached:
            self.ctx.crystal_cache = self._crystal_context(question)
            self.ctx.is_crystal_cached = True
            self.log(f"[STAGE 1] 晶体缓存首次检索 | 共 {len(self.ctx.crystal_cache)} 条", "system")
        else:
            self.log(f"[STAGE 1] ♻️ 晶体缓存命中 | 复用 {len(self.ctx.crystal_cache)} 条", "system")

        shared_context = self.ctx.crystal_cache
        # ===== 证据编排器：构建证据包（内部检索 + 外部缓存，避免网络阻塞） =====
        try:
            self.ctx.evidence_orchestrator = EvidenceOrchestrator(
                self.engine, ai_client=self.ai, log_callback=self.log
            )
            self.ctx.evidence_package = self.ctx.evidence_orchestrator.build_package(
                question, use_network=False
            )
            self.log(
                f"🧩 证据包就绪：{len(self.ctx.evidence_package.items)} 条证据，"
                f"关键词 {len(self.ctx.evidence_package.keywords)}",
                "system",
            )
        except Exception as e:
            self.log(f"⚠️ 证据包构建失败（不影响辩论）：{e}", "warning")
            self.ctx.evidence_package = None
            self.ctx.evidence_orchestrator = None
        # ===== Day 15: 追踪晶体使用 =====
        try:
            # 从 shared_context 中提取使用的晶体ID
            used_crystals = re.findall(r'\[C(\d+)\]', shared_context)
            if used_crystals:
                crystal_ids = [f"C{cid}" for cid in used_crystals]
                self.engine._track_crystal_usage(crystal_ids, context="debate_context")
                self.log(f"📊 追踪到 {len(crystal_ids)} 个晶体被加载到上下文", "system")
        except Exception as e:
            self.log(f"⚠️ 晶体追踪异常：{e}", "warning")

        round1_answers, lark_bare_answer = self._parallel_round0_and_round1(
            question, shared_context, core_roles
        )

        if self._all_answers_failed(round1_answers):
            sample = next((a.get("answer", "") for a in round1_answers), "")
            raise RuntimeError(
                "多角色辩论失败：第 1 轮全部角色调用失败，已终止（避免输出降级废报告）。"
                f"示例错误：{sample[:80]}"
            )

        
        # 记录 Round 0 结果
        round0_answers = [{"role": "百灵鸟（裸模型）", "answer": lark_bare_answer}]
        rounds = [{"round": 0, "answers": round0_answers, "audit": {"summary": "裸模型基线，无审计"}}]
        
        # 审计 Round 1
        _check_alarms_for_round(round1_answers, 1, None)
        current_audit = self._audit(question, round1_answers, round_no=1)
        rounds.append({"round": 1, "answers": round1_answers, "audit": current_audit})
        conflict_streak = 1 if current_audit.get("major_conflict") else 0
        self.ctx.conflict_streak = conflict_streak
        self._emit_progress("Round 0 + Round 1 完成", 30)

        # ===== 判断是否启用 RUMAD =====
        use_rumad = (mode == "debate_full" and self.rumad_enabled)
        if use_rumad:
            self.log("🧠 RUMAD 拓扑控制已启用", "system")
            # 记录第一轮数据用于后续更新
            self._rumad_round_answers[1] = round1_answers
            self._rumad_audits[1] = current_audit

        # ===== 第2轮：引入百灵鸟 =====
        self._emit_progress("生成外部总览", 30)
        external_overview = self._fetch_external_overview(question)
        self._emit_progress("百灵鸟采样", 35)
        lark_answer = self._lark_sampled_opinion(question, external_overview)
        self._emit_progress("第2轮辩论", 40)
        previous_with_lark = round1_answers + [lark_answer]
        round2_answers = self._debate_round(question, shared_context, previous_with_lark, current_audit, 2, all_roles, lark_answer=lark_answer)
        if self._all_answers_failed(round2_answers):
            raise RuntimeError(
                "多角色辩论失败：第 2 轮全部角色调用失败，已终止（避免输出降级废报告）。"
            )
        _check_alarms_for_round(round2_answers, 2, None)
        current_audit = self._audit(question, round2_answers, round_no=2)
        rounds.append({"round": 2, "answers": round2_answers, "audit": current_audit})
        gap_diag = self._diagnose_gaps(question, current_audit, rounds)
        self.ctx.gap_diagnostics = gap_diag
        if gap_diag["gaps"]:
            self.log(f"🧩 缺口选择题：{'、'.join(g['label'] for g in gap_diag['gaps'])}", "warning")
        conflict_streak = conflict_streak + 1 if current_audit.get("major_conflict") else 0
        self.ctx.conflict_streak = conflict_streak
        orchestrator = OutputOrchestrator(self.ai, self.engine)
        self._emit_progress("第2轮完成", 50)

        # ===== 后续轮次：反思 + 辩论 =====
        previous_answers = round2_answers
        round_answers = round2_answers
        for round_no in range(3, max_rounds + 1):
            # ===== Day 8: 法官提前介入 =====
            self._maybe_early_judge(question, rounds, orchestrator, round_no)
            arbitration = self.ctx.arbitration
            conflict_streak = self.ctx.conflict_streak
            # ===== 修改：每轮更新 RUMAD（前3轮warm-up除外） =====
            if use_rumad and round_no > 3:  # 原为 round_no % 2 == 0
                prev_answers = self._rumad_round_answers.get(round_no - 1, [])
                prev_audit = self._rumad_audits.get(round_no - 1, {})

                self.rumad.update_with_result(
                    prev_answers,
                    round_answers,
                    prev_audit,
                    current_audit
                )
                self.log(f"🧠 [RUMAD] 第 {round_no} 轮 Q-learning 更新 | 奖励={self.rumad.last_reward:.3f}", "system")                   
                
                # RUMAD 选择拓扑
                rumad_action = self.rumad.get_topology_decision(
                    prev_answers,
                    round_no - 1,
                    prev_audit
                )
                
                if rumad_action:
                    speaker, target = rumad_action
                    self.ctx.rumad_focus = rumad_action
                    self.log(f"  🧠 RUMAD 拓扑决策: {speaker} 发言 -> 针对 {target}", "system")
                else:
                    self.ctx.rumad_focus = None

            self.log("[STAGE 4] 反思轮启动 | 全员修正立场", "system")            
            self._emit_progress(f"反思第{round_no-1}轮", 55 + round_no * 5)
            reflection_answers = self._reflection_round(question, shared_context, previous_answers, current_audit, all_roles, round_num=round_no-1, arbitration=arbitration)
            reflection_audit = self._audit(question, reflection_answers, round_no=round_no-0.5)
            self._emit_progress(f"第{round_no}轮辩论", 60 + round_no * 5)
            round_answers = self._debate_round(question, shared_context, reflection_answers, reflection_audit, round_no, all_roles, arbitration=arbitration)
            _check_alarms_for_round(round_answers, round_no, None)
            current_audit = self._audit(question, round_answers, round_no=round_no)
            conflict_streak = conflict_streak + 1 if current_audit.get("major_conflict") else 0
            self.ctx.conflict_streak = conflict_streak
            rounds.append({
                "round": round_no,
                "answers": round_answers,
                "audit": current_audit,
                "reflection": reflection_answers,
                "reflection_audit": reflection_audit
            })
            
            # ===== RUMAD 更新（在每轮结束后） =====
            if use_rumad:
                self._rumad_round_answers[round_no] = round_answers
                self._rumad_audits[round_no] = current_audit
                
                # 更新 Q-learning (每2轮更新一次)
                if round_no % 2 == 0 and round_no > 3:
                    prev_answers = self._rumad_round_answers.get(round_no - 2, [])
                    prev_audit = self._rumad_audits.get(round_no - 2, {})
                    
                    self.rumad.update_with_result(
                        prev_answers,
                        round_answers,
                        prev_audit,
                        current_audit
                    )
            
            previous_answers = round_answers
            self._emit_progress(f"第{round_no}轮完成", 70 + round_no * 5)
            jaccard_result = self._check_convergence(round_answers, reflection_answers)
            # 注意：_check_convergence 返回 True/False，但内部计算了 avg_sim，需要改造或重新计算
            # 如果你不想改 _check_convergence，可以在它内部添加日志，或者在这里重新计算一次
            self.log(f"[STAGE 3] ⏹ 收敛判断 | 退出={jaccard_result}", "system")

            if jaccard_result:
                self._emit_progress("收敛完成", 95)
                break

            self.log(f"[STAGE 3] 第 {round_no} 轮对抗辩论启动 | 角色数={len(all_roles)}", "system")
        # ===== Day 13.5: 沉思式反思（在输出前调用） =====
        self._emit_progress("沉思式反思", 85)
        contemplative_result = self._contemplative_reflection(question, rounds)
        wise_echo = contemplative_result.get("wise_echo", "")
        
        # ===== 由 OutputOrchestrator 接管输出 =====
        self._emit_progress("生成结构化输出", 90)

        self.log(f"[STAGE 5] 大法官终审裁决启动 | 输入轮次={len(rounds)}", "system")
        try:
            if "orchestrator" not in locals() or orchestrator is None:
                orchestrator = OutputOrchestrator(self.ai, self.engine)
            final_schema = orchestrator.generate(question, rounds, wise_echo=wise_echo)

            result = {
                "mode": mode,
                "question": question,
                "rounds": rounds,
                "final_schema": final_schema.dict(),
                "board_version": final_schema.board_version,
                "employee_version": final_schema.employee_version,
                "novice_version": final_schema.novice_version,
                "expert_version": final_schema.expert_version,
                "elegant_epilogue": final_schema.elegant_epilogue,
                "decision_annex": final_schema.decision_annex,
                "dashboard_stats": final_schema.dashboard_stats,
                "judge_audit": final_schema.judge_audit,
                "round_by_round": [r.dict() for r in final_schema.round_by_round],
                "answer": final_schema.board_version,
                "calls_estimate": len(all_roles) * 4,
                # ===== Day 0-4 元数据 =====
                "_meta": {
                    "routing": routing_result,
                    "classification": self._current_classification,
                    "cognitive_operators": self._cognitive_operators,
                    "history_reused": self._history_result.get("matched", False) if self._history_result else False,
                    "estimated_tokens": self._token_count,
                    "elapsed_seconds": round(time.time() - self._start_time, 2),
                    "early_arbitration": {
                        "called": self.ctx.judge_early_called,
                        "round": self.ctx.arbitration_round,
                        "verdict": self.ctx.arbitration[:200]
                    }
                },
                # ===== Day 11.5: RUMAD 信息 =====
                "_rumad": {
                    "enabled": self.rumad_enabled,
                    "actions": len(self.rumad.history),
                    "last_action": self.rumad.last_action,
                    "last_reward": self.rumad.last_reward
                }
            }

            # ===== Day 3: 元原语触发链（辩论结束后运行） =====
            try:
                self.log("🧠 运行元原语触发链检查...", "system")
                meta_results = self.engine.meta.run_all_primitives()
                triggered = meta_results.get("triggered_chains", [])
                if triggered:
                    self.log(f"✅ 触发链执行：{len(triggered)} 条链被触发", "success")
                    for chain in triggered:
                        self.log(f"   {chain['chain']}: {chain['source']} → {chain['target']} (通过: {chain['passed']})", "system")
                else:
                    self.log("ℹ️ 无触发链条件满足", "system")
            except Exception as e:
                self.log(f"⚠️ 元原语执行异常：{e}", "warning")

            # ===== Day 5: Hebbian 学习 - 评估有效晶体组合 =====
            try:
                # 收集本轮辩论中所有被引用的晶体 ID
                used_crystal_ids = set()
                for rd in rounds:
                    for answer_item in rd.get("answers", []):
                        text = answer_item.get("answer", "")
                        matches = re.findall(r'\[C(\d+)\]', text)
                        used_crystal_ids.update([f"C{mid}" for mid in matches])

                if used_crystal_ids:
                    # 获取最后一轮的审计评分作为质量信号
                    last_round = rounds[-1] if rounds else {}
                    last_audit = last_round.get("audit", {})
                    ev_scores = list(last_audit.get("evidence_scores", {}).values())
                    if ev_scores:
                        avg_score = sum(ev_scores) / len(ev_scores)
                    else:
                        # 降级：使用审计摘要中的关键词判断
                        summary = last_audit.get("summary", "")
                        if "通过" in summary or "优秀" in summary:
                            avg_score = 0.8
                        elif "一般" in summary:
                            avg_score = 0.5
                        else:
                            avg_score = 0.6

                    # 获取任务类型（九分类多标签）
                    task_categories = self.engine._classify_question(question)

                    # 更新 Hebbian 权重
                    self.engine.update_hebbian_weights(list(used_crystal_ids), score=avg_score, question=question)
                    self.log(f"🧠 Hebbian 学习更新：{len(used_crystal_ids)} 个晶体，"
                             f"分类={task_categories}，评分={avg_score:.2f}", "system")
                    spoke_role_keys = []
                    name_to_key = {r.name: r.key for r in self.roles}
                    for rd in rounds:
                        for item in rd.get("answers", []):
                            rk = name_to_key.get(item.get("role", ""))
                            if rk and rk not in spoke_role_keys:
                                spoke_role_keys.append(rk)
                    try:
                        self.engine.record_hebbian_reward(
                            "activity",
                            crystal_ids=list(used_crystal_ids),
                            role_keys=spoke_role_keys,
                        )
                        self.log("🧠 多说话/复用奖励已计入 Hebbian", "system")
                    except Exception as e:
                        self.log(f"⚠️ Hebbian 多奖励更新失败：{e}", "warning")
                else:
                    self.log("ℹ️ 本轮辩论未引用晶体，跳过 Hebbian 学习", "system")
            except Exception as e:
                self.log(f"⚠️ Hebbian 学习失败：{e}", "warning")

            # ===== Day 8: 双时间尺度进化调度 - 饱和检测 =====
            try:
                # 计算本轮质量评分（从审计评分获取）
                last_round = rounds[-1] if rounds else {}
                last_audit = last_round.get("audit", {})
                ev_scores = list(last_audit.get("evidence_scores", {}).values())
                if ev_scores:
                    quality_score = sum(ev_scores) / len(ev_scores)
                else:
                    summary = last_audit.get("summary", "")
                    if "通过" in summary or "优秀" in summary:
                        quality_score = 0.8
                    elif "一般" in summary:
                        quality_score = 0.5
                    else:
                        quality_score = 0.6

                context = {
                    "modification_type": "prompt",
                    "rounds_count": len(rounds),
                    "question": question
                }
                saturation_result = self.engine.meta.prompt_saturation_detector(quality_score, context)

                if saturation_result.get("is_saturated"):
                    self.log(
                        f"📊 双时间尺度进化调度：本轮质量提升 {saturation_result.get('improvement', 0):.3f}，"
                        f"连续 {saturation_result.get('consecutive_rounds', 0)} 轮饱和，"
                        f"状态：{saturation_result.get('status', 'unknown')}",
                        "system"
                    )
                    if saturation_result.get("level") == "control_logic":
                        self.log(
                            f"📊 双时间尺度进化调度：提示词优化已饱和（连续 {saturation_result.get('consecutive_rounds', 0)} 轮），"
                            f"升级到控制逻辑层面",
                            "system"
                        )
                else:
                    self.log(
                        f"📊 双时间尺度进化调度：本轮质量提升 {saturation_result.get('improvement', 0):.3f}，"
                        f"未饱和（状态：{saturation_result.get('status', 'unknown')}）",
                        "system"
                    )
            except Exception as e:
                self.log(f"⚠️ 饱和检测失败：{e}", "warning")

            # ===== Day 0: 埋点数据统计 =====
            elapsed = time.time() - self._start_time
            self.log(f"📊 辩论耗时：{elapsed:.2f} 秒", "system")
            # ===== 真实 token 用量统计（来自 AIClient.CALL_LOG） =====
            run_call_log = list(AIClient.CALL_LOG[self._call_log_start:])
            usage = aggregate_call_log(run_call_log)
            prompt_total = usage["prompt_tokens"]
            completion_total = usage["completion_tokens"]
            cache_hit = usage["prompt_cache_hit_tokens"]
            cache_miss = usage["prompt_cache_miss_tokens"]
            call_count = usage["calls"]
            estimated_cost = (
                cache_miss * Config.DEEPSEEK_INPUT_MISS_PRICE_PER_M
                + cache_hit * Config.DEEPSEEK_INPUT_HIT_PRICE_PER_M
                + completion_total * Config.DEEPSEEK_OUTPUT_PRICE_PER_M
            ) / 1_000_000
            self._token_count = prompt_total + completion_total
            result["_meta"]["estimated_tokens"] = self._token_count
            result["_token_usage"] = {
                "calls": call_count,
                "prompt_tokens": prompt_total,
                "completion_tokens": completion_total,
                "total_tokens": self._token_count,
                "prompt_cache_hit_tokens": cache_hit,
                "prompt_cache_miss_tokens": cache_miss,
                "by_caller": usage.get("by_caller", {}),
            }
            self.log(
                f"📊 Token消耗：调用 {call_count} 次 | Prompt {prompt_total} / "
                f"Completion {completion_total} / 总 {self._token_count} / "
                f"缓存命中 {cache_hit} / 未命中 {cache_miss}，预估成本：${estimated_cost:.6f}",
                "system",
            )

            # ===== Day 7: 记录帕累托数据 =====
            try:
                # 获取当前模式
                profile_name = getattr(self, '_current_profile', 'balanced')
                if profile_name not in ['high_accuracy', 'balanced', 'economy']:
                    profile_name = 'balanced'

                # 计算本次对话的指标
                accuracy = 0.7  # 默认值，实际应从审计评分获取
                # 尝试从审计评分获取更准确的准确性
                last_round = rounds[-1] if rounds else {}
                last_audit = last_round.get("audit", {})
                ev_scores = list(last_audit.get("evidence_scores", {}).values())
                if ev_scores:
                    accuracy = sum(ev_scores) / len(ev_scores)
                else:
                    # 降级：使用审计摘要判断
                    summary = last_audit.get("summary", "")
                    if "通过" in summary or "优秀" in summary:
                        accuracy = 0.8
                    elif "一般" in summary:
                        accuracy = 0.5

                # 使用真实 usage 估算成本
                cost = estimated_cost

                # 计算延迟
                elapsed = time.time() - self._start_time

                # 统计晶体引用数
                total_refs = 0
                for rd in rounds:
                    for item in rd.get("answers", []):
                        text = item.get("answer", "")
                        total_refs += len(re.findall(r'\[C\d+\]', text))

                # 记录到帕累托跟踪器
                self.engine.meta.record_conversation_metrics(
                    profile_name=profile_name,
                    accuracy=accuracy,
                    cost=cost,
                    latency=elapsed,
                    crystal_refs=total_refs,
                    quality_score=accuracy
                )

                # 记录每日统计
                today = datetime.now().date().isoformat()
                self.engine.meta.record_daily_stats({
                    "date": today,
                    "quality_score": accuracy,
                    "crystal_refs": total_refs,
                    "bias_index": 0.3,  # 默认值
                    "tokens_used": self._token_count
                })

                self.log(f"📊 帕累托数据已记录：模式={profile_name}, 准确性={accuracy:.2f}, 成本=${cost:.6f}", "system")

            except Exception as e:
                self.log(f"⚠️ 帕累托数据记录失败：{e}", "warning")


            # ===== Day 12: 可验证主张提取 + SVR-MAD + 沙盒执行 + M3MAD-Bench =====
            try:
                self.log("🔬 运行 Day 12 验证流程...", "system")
                day12 = Day12Integration(self.engine, self.ai)
                
                # 收集所有回答文本
                all_text = ""
                for rd in rounds:
                    for ans in rd.get("answers", []):
                        all_text += ans.get("answer", "") + "\n"
                
                if all_text.strip():
                    day12_result = day12.process_text(
                        all_text,
                        rounds,
                        decision_annex=result.get("decision_annex") or {},
                        judge_audit=result.get("judge_audit") or {},
                    )
                    result["_day12"] = day12_result
                    
                    claims_count = day12_result.get("claims_extracted", 0)
                    verified_count = day12_result.get("verified_count", 0)
                    m3mad_score = day12_result.get("m3mad_bench", {}).get("overall_score", 0)
                    
                    self.log(f"📊 Day 12 验证完成：提取 {claims_count} 条主张，验证通过 {verified_count} 条，M3MAD评分 {m3mad_score:.2f}", "system")
                    
                    # 将验证摘要添加到 final_schema
                    if "final_schema" in result:
                        schema = result["final_schema"]
                        if hasattr(schema, 'dict'):
                            schema_dict = schema.dict() if hasattr(schema, 'dict') else schema
                        else:
                            schema_dict = schema
                        schema_dict["day12_verification"] = {
                            "claims_count": claims_count,
                            "verified_count": verified_count,
                            "m3mad_score": m3mad_score,
                            "summary": day12_result.get("claim_verification_summary", "")
                        }
                        # 如果有审计信息，也添加上
                        if "judge_audit" in schema_dict:
                            schema_dict["judge_audit"]["sandbox_verification"] = {
                                "claims_verified": verified_count,
                                "total_claims": claims_count,
                                "verification_summary": day12_result.get("claim_verification_summary", "")
                            }
                else:
                    self.log("ℹ️ 无足够文本内容，跳过 Day 12 验证", "system")
                    
            except Exception as e:
                self.log(f"⚠️ Day 12 验证流程异常：{e}", "warning")
                import traceback
                traceback.print_exc()

            self.log(f"result 包含 _day12: {'_day12' in result}", "debug")
            # ===== 证据编排器：算术自洽门 + 假设分级 + 可信度报告 =====
            try:
                orchestrator = getattr(self.ctx, "evidence_orchestrator", None)
                if orchestrator is None:
                    orchestrator = EvidenceOrchestrator(
                        self.engine, ai_client=self.ai, log_callback=self.log
                    )
                    if hasattr(self, "ctx"):
                        self.ctx.evidence_orchestrator = orchestrator
                all_evidence_text = ""
                for rd in rounds:
                    for ans in rd.get("answers", []):
                        all_evidence_text += ans.get("answer", "") + "\n"
                if all_evidence_text.strip():
                    evidence_report = orchestrator.build_report(
                        all_evidence_text,
                        question,
                        getattr(self.ctx, "evidence_package", None) if hasattr(self, "ctx") else None,
                    )
                    result["_evidence"] = evidence_report
                    if "final_schema" in result:
                        schema = result["final_schema"]
                        schema_dict = schema.dict() if hasattr(schema, "dict") else schema
                        schema_dict["evidence_report"] = evidence_report
                    self.log(
                        f"🧩 证据报告完成：主张 {evidence_report['claim_verification'].get('total', 0)} 条，"
                        f"算术门 {evidence_report['arithmetic_gates'].get('passed', 0)}/"
                        f"{evidence_report['arithmetic_gates'].get('total', 0)} 通过，"
                        f"假设 {len(evidence_report.get('assumption_grading', []))} 条",
                        "system",
                    )
            except Exception as e:
                self.log(f"⚠️ 证据报告生成失败：{e}", "warning")
            # ===== Day 13: 强制沉淀管道 - 提取 L1/L2/L3 结论 =====
            try:
                self.log("📦 执行强制沉淀管道...", "system")
                deposit_result = self._extract_conclusion_layers(question, rounds)
                result["_deposit"] = deposit_result

                # 保存沉淀数据到文件，供 GUI 读取
                import json
                deposit_path = Config.DATA_ROOT / "系统日志" / "last_deposit.json"
                deposit_path.parent.mkdir(parents=True, exist_ok=True)
                with open(deposit_path, "w", encoding="utf-8") as f:
                    json.dump(deposit_result, f, ensure_ascii=False, indent=2)

                if deposit_result.get("unarchived_holes"):
                    self.log(f"⚠️ 发现 {len(deposit_result['unarchived_holes'])} 个未归档的 L3 孔洞，会话将被锁定", "warning")
                    for hole in deposit_result["unarchived_holes"][:3]:
                        self.log(f"   - {hole['id']}: {hole['content'][:50]}...", "system")
                    self.engine.log_evolution_event(
                        "deposit_unarchived_holes",
                        {
                            "count": len(deposit_result["unarchived_holes"]),
                            "holes": deposit_result["unarchived_holes"],
                            "trigger": "debate_complete"
                        }
                    )
                else:
                    self.log("✅ 所有结论已封装，无未归档孔洞", "success")
            except Exception as e:
                self.log(f"⚠️ 强制沉淀管道异常：{e}", "warning")
                import traceback
                traceback.print_exc()


                
            self._emit_progress("完成", 100)
            self.log("✅ V3.0 结构化输出生成完成", "success")           

            # 记录本次辩论质量（用于自我修复）
            try:
                # 从审计评分估算质量
                last_round = rounds[-1] if rounds else {}
                audit = last_round.get("audit", {})
                ev_scores = list(audit.get("evidence_scores", {}).values())
                if ev_scores:
                    quality = sum(ev_scores) / len(ev_scores)
                else:
                    quality = 0.5  # 默认
                self.engine.record_dialogue_quality(quality, {"question": question})
            except Exception:
                pass  # 静默
            return result

        except Exception as e:
            self.log(f"⚠️ OutputOrchestrator 执行失败: {e}，降级返回原始数据", "error")
            
            import traceback
            traceback.print_exc()
            return {
                "mode": mode,
                "question": question,
                "rounds": rounds,
                "answer": "（输出生成失败，请查看原始辩论数据）",
                "calls_estimate": len(all_roles) * 4,
                "error": str(e),
                "_rumad": {
                    "enabled": self.rumad_enabled,
                    "actions": len(self.rumad.history),
                    "last_action": self.rumad.last_action,
                    "last_reward": self.rumad.last_reward
                }
            }



    # ===== 补全专家方案遗漏的 _run_lark_bare 方法 =====
    def _run_lark_bare(self, question: str) -> str:
        """百灵鸟裸模型基线（完全不依赖晶体树和角色提示）"""
        prompt = f"请直接回答以下问题，给出你最直观、最完整的答案。\n\n问题：{question}"
        raw_answer = self.ai.chat(prompt, system="你是一位知识广博的通用AI，请直接输出完整回答。")
        # 若字数不足，强制补充展开
        if count_output_words(raw_answer) < 400:
            expand = self.ai.chat(
                f"请将以下回答扩展为更详细的论述（至少800字）：\n{raw_answer}",
                system="请只输出扩展后的正文。"
            )
            return expand
        return raw_answer

    def _extract_conclusion_layers(self, question: str, rounds: List[Dict]) -> Dict[str, Any]:
        """
        从辩论结果中提取 L1/L2/L3 结论（强制沉淀管道）

        L1: 核心结论（必须采纳的决策）
        L2: 重要建议（条件性采纳）
        L3: 待验证问题（需要进一步探索的孔洞）
        """
        if not rounds:
            return {"error": "无辩论数据"}

        last_round = rounds[-1]
        answers = last_round.get("answers", [])

        all_text = ""
        for ans in answers:
            all_text += ans.get("answer", "") + "\n"

        if not all_text.strip():
            return self._fallback_extract_conclusion(question, rounds)

        prompt = f"""
请从以下辩论记录中提取三层结论：

【辩论问题】
{question}

【辩论记录摘要】
{all_text[:3000]}

【输出要求】
请只返回 JSON，格式如下：
{{
    "L1_conclusions": [
        {{"id": "L1-001", "content": "核心结论1（必须采纳的决策）", "source": "来源角色"}}
    ],
    "L2_conclusions": [
        {{"id": "L2-001", "content": "重要建议1（条件性采纳）", "source": "来源角色"}}
    ],
    "L3_holes": [
        {{"id": "H-001", "content": "待验证问题1（需要进一步探索）", "urgency": 0.7}}
    ]
}}

规则：
- L1：不超过3条，每条不超过50字
- L2：不超过5条，每条不超过80字
- L3：不超过5条，每条不超过60字
- urgency: 0.5-1.0，表示紧迫程度
- unarchived_holes: 从 L3 中筛选 urgency >= 0.7 的孔洞
"""
        try:
            result = self.ai.chat_json(prompt, temperature=0.3)
            if "error" in result:
                return self._fallback_extract_conclusion(question, rounds)

            result.setdefault("L1_conclusions", [])
            result.setdefault("L2_conclusions", [])
            result.setdefault("L3_holes", [])

            # 生成 unarchived_holes
            unarchived = []
            for hole in result.get("L3_holes", []):
                if hole.get("urgency", 0) >= 0.7:
                    unarchived.append({
                        "id": hole.get("id", f"H-{len(unarchived)+1:03d}"),
                        "content": hole.get("content", ""),
                        "urgency": hole.get("urgency", 0.7)
                    })
            result["unarchived_holes"] = unarchived

            return result
        except Exception as e:
            self.log(f"⚠️ AI 提取结论失败，使用降级方案: {e}", "warning")
            return self._fallback_extract_conclusion(question, rounds)

    def _fallback_extract_conclusion(self, question: str, rounds: List[Dict]) -> Dict[str, Any]:
        """降级方案：从最后一轮的大法官裁决中提取"""
        if not rounds:
            return {"L1_conclusions": [], "L2_conclusions": [], "L3_holes": [], "unarchived_holes": []}

        last_round = rounds[-1]
        audit = last_round.get("audit", {})
        final_verdict = audit.get("summary", "")

        l1 = []
        l2 = []
        l3 = []

        sentences = re.split(r'[。！？；]', final_verdict)
        for i, sent in enumerate(sentences[:10]):
            sent = sent.strip()
            if not sent:
                continue
            if any(kw in sent for kw in ["核心", "关键", "必须", "首要", "根本"]):
                l1.append({"id": f"L1-{i+1:03d}", "content": sent[:50], "source": "大法官"})
            elif any(kw in sent for kw in ["建议", "可以考虑", "有条件", "如果"]):
                l2.append({"id": f"L2-{i+1:03d}", "content": sent[:80], "source": "大法官"})
            else:
                l3.append({"id": f"H-{i+1:03d}", "content": sent[:60], "urgency": 0.5})

        l1 = l1[:3]
        l2 = l2[:5]
        l3 = l3[:5]

        unarchived = [h for h in l3 if h.get("urgency", 0) >= 0.7]

        return {
            "L1_conclusions": l1,
            "L2_conclusions": l2,
            "L3_holes": l3,
            "unarchived_holes": unarchived
        }
    # ===== Day 11.5: RUMAD 启用/禁用方法 =====
    # ⬇️⬇️⬇️ 在这里插入以下三个方法 ⬇️⬇️⬇️

    def enable_rumad(self):
        """启用 RUMAD 拓扑控制"""
        self.rumad_enabled = True
        self.rumad.set_enabled(True)
        self.log("🧠 RUMAD 拓扑控制已启用", "system")

    def disable_rumad(self):
        """禁用 RUMAD 拓扑控制"""
        self.rumad_enabled = False
        self.rumad.set_enabled(False)
        self.log("🧠 RUMAD 拓扑控制已禁用", "system")

    def get_rumad_stats(self) -> Dict:
        """获取 RUMAD 统计信息"""
        return self.rumad.get_stats()

    # ⬆️⬆️⬆️ 插入结束 ⬆️⬆️⬆️


    # ==================== 工具方法 ====================
    def _tokens(self, text: str) -> set:
        stop = {"的", "了", "和", "是", "我", "一个", "这个", "那个", "如何", "什么", "为什么", "我们", "你们", "他们"}
        tokens = set()
        for word in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text.lower()):
            if re.search(r"[\u4e00-\u9fff]", word):
                tokens.update(word[i:i + 2] for i in range(len(word) - 1))
            elif len(word) >= 3:
                tokens.add(word)
        return {token for token in tokens if token and token not in stop}

    def _jaccard(self, a: str, b: str) -> float:
        ta, tb = self._tokens(a), self._tokens(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    def _average_jaccard(self, answers: List[str]) -> float:
        pairs = list(itertools.combinations(answers, 2))
        if not pairs:
            return 0.0
        return sum(self._jaccard(a, b) for a, b in pairs) / len(pairs)

    # ===== Day 1 新增：警报处理辅助方法 =====
    def _inject_external_knowledge(self, alarm: dict):
        """注入外部知识到审计上下文，让本轮审计更有事实依据。"""
        question = self.ctx.current_question
        if not question:
            return
        overview = self._fetch_external_overview(question)
        if overview and len(overview) > 20:
            self.ctx.audit_external_context = overview
        self.log("  外部知识已注入审计上下文，供本轮审计参考", "system")

    def _review_unreliable_outputs(self, alarm: dict):
        """重审不可靠输出：基于原回答与外部总览逐条修正并回写本轮答案。"""
        answers = getattr(self.ctx, "last_round_answers", None) or []
        overview = getattr(self.ctx, "audit_external_context", "") or ""
        crystal_context = getattr(self.ctx, "crystal_cache", "") or ""
        evidence_context = ""
        package = getattr(self.ctx, "evidence_package", None)
        if package is not None:
            try:
                evidence_context = package.format_for_prompt()
            except Exception:
                evidence_context = ""
        unreliable = [
            item for item in answers
            if item.get("answer") and not _is_reliable_output(item.get("answer", ""))
        ]
        if not unreliable:
            return
        for item in unreliable:
            role = item.get("role", "未知")
            original = item.get("answer", "")
            review_prompt = (
                f"你正在重审【{role}】的输出。原回答可能存在截断、占位或错误标记，"
                f"请基于事实修正为完整回答。\n\n"
                f"【原回答】\n{original}\n\n"
                f"【外部事实参考】\n{overview or '（无）'}\n\n"
                f"【晶体/证据参考】\n{crystal_context or '（无）'}\n\n{evidence_context}\n\n"
                f"要求：保留原有核心观点；修复截断、占位、错误标记；"
                f"保留原回答中的引用编号；如果原回答没有引用，请从晶体/证据参考中补上相关 [Cxxx]；"
                f"补全为结构完整、以正常标点收尾的正文；不要解释过程，直接输出修正后的完整正文。"
            )
            corrected = self.ai.chat(review_prompt)
            if corrected and isinstance(corrected, str) and len(corrected.strip()) > 10:
                refs = re.findall(
                    r"\[C\d+\]|\[E\d+\]|\[(?:arxiv|news|hf|external)\]",
                    original,
                )
                if refs:
                    missing = [ref for ref in refs if ref not in corrected]
                    if missing:
                        corrected = (
                            corrected.rstrip()
                            + "\n\n【保留引用】"
                            + "、".join(missing[:3])
                            + "。"
                        )
                item["answer"] = corrected.strip()
                self.log(
                    f"🔄 {role} 不可靠输出已重审修正（{count_output_words(item['answer'])}字）",
                    "warning",
                )

    def _record_failure_trace(self, question: str, failure_type: str, context: Dict) -> None:
        """
        记录失败轨迹，供后续历史检索使用

        Args:
            question: 当前问题
            failure_type: 失败类型（如 "low_crystal_reference", "audit_failed", "debate_diverged"）
            context: 失败上下文，包含失败时的各项指标
        """
        trace = {
            "question": question,
            "failure_type": failure_type,
            "timestamp": datetime.now().isoformat(),
            "context": context,
        }
        # 如果上下文中有有效晶体组合，也记录下来
        effective_crystals = context.get("effective_crystals", [])
        if effective_crystals:
            trace["effective_crystals"] = effective_crystals

        # 记录到 evolution_log
        self.engine.log_evolution_event(
            "failure_trace",
            {
                "failure_traces": trace,
                "trigger": "system_auto",
                "question": question,
                "effective_crystals": effective_crystals
            }
        )
        self.log(f"📝 失败轨迹已记录：{failure_type}", "system")
    def _inject_perspective(self, alarm: dict):
        """强制注入对立视角：添加一个临时角色或修改系统指令"""
        # 可以添加一个“对抗者”角色，或者修改系统提示要求从对立面思考
        self._forced_perspective = "请从与之前所有角色截然相反的角度重新审视问题，提出颠覆性观点。"
        self.log("  对立视角已注入，将在下一轮生效", "system")

    def _trigger_search(self, alarm: dict):
        """强制触发外部搜索并注入审计上下文。"""
        question = self.ctx.current_question
        if not question:
            return
        overview = self._fetch_external_overview(question)
        if overview and len(overview) > 20:
            self.ctx.audit_external_context = overview
        self.log("  外部搜索已触发并注入审计上下文", "system")

    # ===== Day 13.5: 沉思式反思 =====

    def _contemplative_reflection(self, question: str, rounds: List[Dict]) -> Dict[str, Any]:
        """
        执行沉思式反思
        在输出最终报告前调用，生成"智慧回响"
        """
        try:
            self.log("🧘 启动沉思式反思...", "system")
            contemplative = ContemplativeEngine(self.ai, self.engine)
            result = contemplative.reflect(question, rounds)

            # 记录到进化日志
            self.engine.log_evolution_event(
                "contemplative_reflection",
                {
                    "trigger": "debate_complete",
                    "mindfulness": result.get("mindfulness", "")[:100],
                    "emptiness": result.get("emptiness", "")[:100],
                    "non_duality": result.get("non_duality", "")[:100],
                    "boundless_care": result.get("boundless_care", "")[:100],
                    "wise_echo": result.get("wise_echo", "")[:200]
                }
            )

            self.log("✅ 沉思式反思完成，智慧回响已生成", "success")
            return result

        except Exception as e:
            self.log(f"⚠️ 沉思式反思异常：{e}", "warning")
            import traceback
            traceback.print_exc()
            return {
                "wise_echo": "（智慧回响生成中）",
                "trigger": "contemplative_reflection_failed"
            }

    def _inject_language_style_to_prompt(self, prompt: str) -> str:
        """
        将语言风格偏好注入到提示词中
        """
        try:
            fingerprint = self.engine.fingerprint_extractor.get_fingerprint()
            lang = fingerprint.language_style

            style_hint = ""

            # 文白比例
            wenbai = lang.get("wenbai_ratio", "balanced")
            if wenbai == "wen":
                style_hint += "\n【语言风格偏好】请使用偏文言的表达方式，语言典雅庄重。适当使用'之乎者也'等文言虚词。\n"
            elif wenbai == "bai":
                style_hint += "\n【语言风格偏好】请使用白话表达，语言亲切自然，像与朋友交谈。\n"
            else:
                style_hint += "\n【语言风格偏好】请文白相间，既有文言的气韵，又有白话的亲切。\n"

            # 隐喻偏好
            metaphor = lang.get("metaphor_preference", "nature")
            metaphor_map = {
                "nature": "山水自然（如月、竹、云、水、山）",
                "architecture": "建筑空间（如楼、台、亭、阁、桥）",
                "military": "兵家意象（如棋、阵、剑、策、势）",
                "balanced": "自然与人文意象并重"
            }
            style_hint += f"【隐喻偏好】请善用{metaphor_map.get(metaphor, '自然意象')}作为比喻和象征。\n"

            # 节奏偏好
            rhythm = lang.get("rhythm_preference", "balanced")
            rhythm_map = {
                "short": "短句快节奏，如疾风骤雨，干脆有力",
                "long": "长句慢节奏，如大江大河，从容绵长",
                "balanced": "长短句相间，如行云流水，自然流畅"
            }
            style_hint += f"【节奏偏好】{rhythm_map.get(rhythm, '长短句相间')}\n"

            # 文化根基
            roots = lang.get("cultural_roots", ["儒家", "道家"])
            style_hint += f"【文化根基】可自然融入{'、'.join(roots)}的思想意境\n"

            # 注入到提示词中（在末尾添加）
            prompt = prompt + "\n\n" + style_hint

        except Exception as e:
            self.log(f"⚠️ 语言风格注入失败：{e}", "warning")

        return prompt

    def _format_process_summary(self, rounds: List[Dict]) -> str:
        lines = []
        for item in rounds:
            round_no = item.get("round")
            lines.append(f"第 {round_no} 轮：")
            audit = item.get("audit") or {}
            if audit.get("summary"):
                lines.append(f"- 逻辑检查员：{audit.get('summary')}")
            answers = item.get("answers") or []
            for answer in answers:
                text = re.sub(r"\s+", " ", str(answer.get("answer", ""))).strip()
                lines.append(f"- {answer.get('role')}：{text[:180]}{'...' if len(text) > 180 else ''}")
        return "\n".join(lines)

    # ===== 新增工具方法：角色名称转key =====
    def _map_role_key(self, name: str) -> str:
        mapping = {
            "激进者": "radical", 
            "保守者": "conservative", 
            "结构主义者": "structural",
            "百灵鸟": "lark", 
            "取经者": "pilgrim", 
            "奇谋者": "strategist",
            "延安智者": "statesman", 
            "大法官": "judge", 
            "首席发言人": "spokesperson",
            "替身-我": "twin"
        }
        return mapping.get(name, name)

    # ===== Day 0 运行时自检断言 =====
    def _run_day0_runtime_assertions(self):
        """Day 0 运行时自检断言"""
        assertions = [
            ("CrystalEngine 存在", hasattr(self, 'engine')),
            ("MetaLayer 存在", hasattr(self.engine, 'meta')),
            ("CheapGate 存在", hasattr(self.engine, 'cheap_gate')),
            ("FingerprintExtractor 存在", hasattr(self.engine, 'fingerprint_extractor')),
            ("VectorStore 存在", hasattr(self.engine, 'vector_store')),
            ("AlarmMonitor 可用", hasattr(self, 'alarm_monitor')),
        ]
        all_passed = True
        for name, passed in assertions:
            if not passed:
                self.log(f"❌ 自检断言失败：{name}", "error")
                all_passed = False
        if all_passed:
            self.log("✅ Day 0 运行时自检断言全部通过", "system")
        return all_passed

    # ===== 替身自我博弈 =====
    def _run_self_play(self, question: str, max_rounds: int = 2) -> Dict:
        """替身自我博弈主流程"""
        # ===== 进度初始化 =====
        self._emit_progress("启动替身自我博弈", 0)

        roles = self.get_roles_with_twin(include_twin=True)
        twin = next((r for r in roles if r.key == "twin"), None)
        radical = next((r for r in roles if r.key == "radical"), None)
        conservative = next((r for r in roles if r.key == "conservative"), None)
        structural = next((r for r in roles if r.key == "structural"), None)

        if not twin or not radical or not conservative:
            self.log("[WARN] 缺少必要角色，降级到标准辩论", "warning")
            return self.run(question, mode="debate_full", max_rounds=max_rounds)

        crystal_context = self._crystal_context(question)
        rounds_data = []
        all_answers = []

        # ===== Round 1: 激进者 vs 替身-我 =====
        self._emit_progress("第1轮：替身生成观点", 20)
        self.log("[ROUND 1] 激进者攻击替身观点", "system")
        round1_answers = []

        self.log("  替身-我 正在生成观点...", "system")
        twin_prompt = f"用户问题：{question}\n请以替身身份给出独立观点，体现你的认知特征。"
        twin_answer = self.ai.chat(twin_prompt, system=self._role_system(twin, crystal_context))
        round1_answers.append({"role": twin.name, "answer": twin_answer})

        self._emit_progress("第1轮：激进者攻击", 30)
        self.log("  激进者 正在攻击...", "system")
        radical_prompt = f"""用户问题：{question}

替身-我的观点：
{twin_answer}

请作为激进者，攻击替身观点中的默认前提、逻辑漏洞和认知盲区。"""
        radical_answer = self.ai.chat(radical_prompt, system=self._role_system(radical, crystal_context))
        round1_answers.append({"role": radical.name, "answer": radical_answer})

        self._emit_progress("第1轮审计", 40)
        audit1 = self._audit(question, round1_answers, round_no=1)
        jaccard1 = self._average_jaccard([item["answer"] for item in round1_answers])
        rounds_data.append({"round": 1, "answers": round1_answers, "audit": audit1, "jaccard": round(jaccard1, 3)})
        all_answers.extend(round1_answers)

        # ===== Round 2: 替身-我 vs 保守者 =====
        self._emit_progress("第2轮：替身辩护", 55)
        self.log("[ROUND 2] 替身辩护 vs 保守者质疑", "system")
        round2_answers = []

        self.log("  替身-我 正在辩护...", "system")
        twin_defense_prompt = f"""用户问题：{question}

激进者的攻击：
{radical_answer}

审计员反馈：
{audit1.get('summary', '无')}

请作为替身-我，进行辩护并修正观点。"""
        twin_defense = self.ai.chat(twin_defense_prompt, system=self._role_system(twin, crystal_context))
        round2_answers.append({"role": twin.name, "answer": twin_defense})

        self._emit_progress("第2轮：保守者质疑", 65)
        self.log("  保守者 正在质疑...", "system")
        conservative_prompt = f"""用户问题：{question}

替身-我的观点：
{twin_defense}

请作为保守者，从风险、成本、边界角度提出质疑。"""
        conservative_answer = self.ai.chat(conservative_prompt, system=self._role_system(conservative, crystal_context))
        round2_answers.append({"role": conservative.name, "answer": conservative_answer})

        self._emit_progress("第2轮审计", 75)
        audit2 = self._audit(question, round2_answers, round_no=2)
        jaccard2 = self._average_jaccard([item["answer"] for item in round2_answers])
        rounds_data.append({"round": 2, "answers": round2_answers, "audit": audit2, "jaccard": round(jaccard2, 3)})
        all_answers.extend(round2_answers)

        # ===== Round 3: 结构主义者融合 =====
        self._emit_progress("第3轮：结构主义者融合", 85)
        self.log("[ROUND 3] 结构主义者融合各方观点", "system")
        round3_answers = []

        all_text = "\n\n".join([f"### {item['role']}\n{item['answer']}" for item in all_answers])
        structural_prompt = f"""用户问题：{question}

所有辩论观点：
{all_text}

审计摘要：
- 第1轮：{audit1.get('summary', '')}
- 第2轮：{audit2.get('summary', '')}

请作为结构主义者，融合所有观点，输出综合方案。"""
        structural_answer = self.ai.chat(structural_prompt, system=self._role_system(structural, crystal_context))
        round3_answers.append({"role": structural.name, "answer": structural_answer})

        audit3 = self._audit(question, round3_answers, round_no=3)
        jaccard3 = self._average_jaccard([item["answer"] for item in round3_answers])
        rounds_data.append({"round": 3, "answers": round3_answers, "audit": audit3, "jaccard": round(jaccard3, 3)})

        # ===== 总结 =====
        self._emit_progress("总结生成中", 92)
        self.log("[FINAL] 发言人生成最终答案", "system")
        final = self._spokesperson(question, rounds_data, crystal_context, light=False)

        self._emit_progress("完成", 100)
        # Day 5: Hebbian 学习 - 评估有效晶体组合
        try:
            used_crystal_ids = set()
            for round_data in rounds_data:
                for answer_item in round_data.get("answers", []):
                    text = answer_item.get("answer", "")
                    matches = re.findall(r'\[C(\d+)\]', text)
                    used_crystal_ids.update([f"C{mid}" for mid in matches])
            if used_crystal_ids:
                last_audit = rounds_data[-1].get("audit", {})
                ev_scores = list(last_audit.get("evidence_scores", {}).values())
                if ev_scores:
                    avg_score = sum(ev_scores) / len(ev_scores)
                else:
                    avg_score = 0.6
                task_categories = self.engine._classify_question(question)
                self.engine.update_hebbian_weights(list(used_crystal_ids), score=avg_score, question=question)
                self.log(f"🧠 Hebbian 学习更新：{len(used_crystal_ids)} 个晶体，分类={task_categories}，评分={avg_score:.2f}", "system")
        except Exception as e:
            self.log(f"⚠️ Hebbian 学习失败：{e}", "warning")
        return self._result(question, "twin_self_play", rounds_data, final, calls_estimate=7)

# =============================================================================
# Day 0 基线采集运行器
# =============================================================================
