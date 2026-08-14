#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from core.models import CognitiveFingerprint

class FingerprintExtractor:
    """
    认知指纹提取引擎

    从用户的历史对话、辩论参与、晶体化行为中提取认知指纹。
    让系统从"知道你说过什么"升级为"知道你怎么想"。

    对应四阶路径中的"认识你"阶段。
    """

    def __init__(self, engine: Any, file_io: Any):
        self.engine = engine
        self.files = file_io

    def extract(self, history: List[Tuple[str, str]], debate_logs: List[Dict] = None, increment_interactions: int = 0) -> CognitiveFingerprint:
        """
        从对话历史和辩论日志中提取认知指纹

        Args:
            history: 对话历史列表 [(role, content), ...]
            debate_logs: 辩论日志列表（可选）

        Returns:
            CognitiveFingerprint: 提取的认知指纹
        """
        # 加载现有指纹（用于增量更新）
        existing_data = self.files.read_fingerprint()
        existing = CognitiveFingerprint.from_dict(existing_data.get("fingerprint", {}))

        # 如果没有历史数据，返回现有指纹
        if not history:
            return existing

        # 1. 分析用户提问中的关键词 → 风险偏好 + 创新偏好
        risk_score, innovation_score = self._analyze_keywords(history)

        # 2. 分析角色采纳历史 → 偏好角色
        preferred_role, role_history = self._analyze_role_adoption(history, debate_logs)

        # 3. 分析决策果断值
        decisiveness = self._analyze_decisiveness(history)

        # 4. 分析冲突解决风格
        conflict_style = self._analyze_conflict_style(history)

        # 5. 分析注意力模式
        attention_span = self._analyze_attention(history)

        # 6. 计算置信度（数据越多置信度越高）
        # total_interactions = len([msg for msg in history if msg[0] == "user"])
        if increment_interactions > 0:
            new_interactions = increment_interactions
        else:
            new_interactions = len([msg for msg in history if msg[0] == "user"])
            if new_interactions > 0:
                print("⚠️ Warning: extract() called without increment_interactions, using full history count, may cause double counting.")
        total_interactions = existing.total_interactions + new_interactions
        confidence = min(0.9, 0.3 + total_interactions * 0.01)

        # 7. 使用平滑更新
        new_risk = self._smooth_update(existing.risk_tolerance, risk_score, 0.3)
        new_innovation = self._smooth_update(existing.innovation_preference, innovation_score, 0.3)
        new_decisiveness = self._smooth_update(existing.decisiveness, decisiveness, 0.3)
        new_attention = self._smooth_update(existing.attention_span, attention_span, 0.3)
        new_preferred = preferred_role or existing.preferred_role
        new_conflict = conflict_style or existing.conflict_resolution_style
        new_role_history = self._merge_role_history(existing.role_adoption_history, role_history)

        # 8. 构建演化日志
        changes = []
        if abs(existing.risk_tolerance - new_risk) > 0.05:
            changes.append({"dimension": "risk_tolerance", "old": existing.risk_tolerance, "new": new_risk})
        if abs(existing.innovation_preference - new_innovation) > 0.05:
            changes.append({"dimension": "innovation_preference", "old": existing.innovation_preference, "new": new_innovation})
        if abs(existing.decisiveness - new_decisiveness) > 0.05:
            changes.append({"dimension": "decisiveness", "old": existing.decisiveness, "new": new_decisiveness})
        if existing.preferred_role != new_preferred:
            changes.append({"dimension": "preferred_role", "old": existing.preferred_role, "new": new_preferred})

        old_logs = existing.evolution_log[-15:] if existing.evolution_log else []
        evolution_log = old_logs + [{
            "timestamp": datetime.now().isoformat(),
            "changes": changes,
            "total_interactions": existing.total_interactions + total_interactions
        }]
        # Day 2.5: 认知风格分析
        style_result = self._analyze_thinking_style(history)
        new_reasoning = style_result["reasoning_style"]
        new_analogy = style_result["analogy_preference"]
        new_output = style_result["output_style"]
        # Day 13.8: 语言风格分析
        language_style = self._analyze_language_style(history)        
        # 数据不足时保留旧值，避免波动
        if len([msg for msg in history if msg[0] == "user"]) < 5:
            new_reasoning = existing.reasoning_style
            new_analogy = existing.analogy_preference
            new_output = existing.output_style
            language_style = existing.language_style

        # 9. 构建新的指纹对象
        new_fingerprint = CognitiveFingerprint(
            risk_tolerance=new_risk,
            innovation_preference=new_innovation,
            decisiveness=new_decisiveness,
            preferred_role=new_preferred,
            role_adoption_history=new_role_history,
            conflict_resolution_style=new_conflict,
            attention_span=new_attention,
            context_preference=existing.context_preference,
            reasoning_style=new_reasoning,
            analogy_preference=new_analogy,
            output_style=new_output,
            language_style=language_style,  # ← 新增
            last_updated=datetime.now().isoformat(),
            total_interactions=existing.total_interactions + total_interactions,
            confidence=confidence,
            evolution_log=evolution_log
        )

        # 10. 保存更新后的指纹
        # 10. 保存更新后的指纹
        self._save_fingerprint(new_fingerprint)

        # ===== 新增：记录指纹变化进化事件 =====
        if existing.total_interactions > 0:  # 非首次提取
            changes = []
            if abs(existing.risk_tolerance - new_fingerprint.risk_tolerance) > 0.05:
                changes.append({"dimension": "risk_tolerance", "old": existing.risk_tolerance, "new": new_fingerprint.risk_tolerance})
            if abs(existing.innovation_preference - new_fingerprint.innovation_preference) > 0.05:
                changes.append({"dimension": "innovation_preference", "old": existing.innovation_preference, "new": new_fingerprint.innovation_preference})
            if abs(existing.decisiveness - new_fingerprint.decisiveness) > 0.05:
                changes.append({"dimension": "decisiveness", "old": existing.decisiveness, "new": new_fingerprint.decisiveness})
            if existing.preferred_role != new_fingerprint.preferred_role:
                changes.append({"dimension": "preferred_role", "old": existing.preferred_role, "new": new_fingerprint.preferred_role})
            if changes:
                self.engine.log_evolution_event(
                    "fingerprint_changed",
                    {
                        "changes": changes,
                        "confidence": new_fingerprint.confidence,
                        "total_interactions": new_fingerprint.total_interactions,
                        "trigger": "conversation_analysis"
                    }
                )

        return new_fingerprint

    def _analyze_keywords(self, history: List[Tuple[str, str]]) -> Tuple[float, float]:
        """
        分析用户提问中的关键词 → 风险容忍度 + 创新偏好

        风险关键词: 万一, 风险, 成本, 失败, 安全, 稳健, 保守, 验证, 谨慎, 稳妥
        创新关键词: 机会, 突破, 创新, 颠覆, 潜力, 激进, 大胆, 尝试, 新的, 探索
        """
        risk_words = ["万一", "风险", "成本", "失败", "安全", "稳健", "保守", "验证", "谨慎", "稳妥"]
        innovation_words = ["机会", "突破", "创新", "颠覆", "潜力", "激进", "大胆", "尝试", "新的", "探索"]

        user_messages = [msg[1] for msg in history if msg[0] == "user"]
        if not user_messages:
            return 0.5, 0.5

        combined = " ".join(user_messages)
        risk_count = sum(1 for w in risk_words if w in combined)
        innovation_count = sum(1 for w in innovation_words if w in combined)

        total = risk_count + innovation_count
        if total == 0:
            return 0.5, 0.5

        risk_score = min(1.0, risk_count / max(1, len(user_messages)) * 3)
        innovation_score = min(1.0, innovation_count / max(1, len(user_messages)) * 3)

        return risk_score, innovation_score

    def _analyze_role_adoption(self, history: List[Tuple[str, str]], debate_logs: List[Dict] = None) -> Tuple[str, Dict[str, int]]:
        """
        分析用户对辩论角色的采纳偏好
        """
        role_history = {}

        # 从辩论日志中分析
        if debate_logs:
            for log in debate_logs:
                for role in ["激进者", "保守者", "结构主义者", "执行者", "审计者"]:
                    if role in log.get("user_feedback", ""):
                        role_history[role] = role_history.get(role, 0) + 1

        # 从对话历史中分析（关键词匹配）
        user_messages = [msg[1] for msg in history if msg[0] == "user"]
        for msg in user_messages:
            if "激进" in msg or "颠覆" in msg:
                role_history["激进者"] = role_history.get("激进者", 0) + 0.5
            if "保守" in msg or "稳健" in msg:
                role_history["保守者"] = role_history.get("保守者", 0) + 0.5
            if "结构" in msg or "系统" in msg or "框架" in msg:
                role_history["结构主义者"] = role_history.get("结构主义者", 0) + 0.5
            if "执行" in msg or "步骤" in msg or "操作" in msg:
                role_history["执行者"] = role_history.get("执行者", 0) + 0.5
            if "审计" in msg or "验证" in msg or "检查" in msg:
                role_history["审计者"] = role_history.get("审计者", 0) + 0.5

        if not role_history:
            return "structural", {}

        preferred = max(role_history.items(), key=lambda x: x[1])[0]
        return preferred, role_history

    def _analyze_decisiveness(self, history: List[Tuple[str, str]]) -> float:
        """
        分析决策果断值
        通过用户是否快速追问、是否打断、是否快速确认来判断
        """
        user_messages = [msg[1] for msg in history if msg[0] == "user"]
        if len(user_messages) < 3:
            return 0.5

        short_count = sum(1 for msg in user_messages if len(msg) < 20)
        short_ratio = short_count / len(user_messages)

        confirm_words = ["好的", "对", "是", "行", "可以", "同意", "确认", "就这样"]
        confirm_count = sum(1 for msg in user_messages if any(w in msg for w in confirm_words))
        confirm_ratio = confirm_count / len(user_messages)

        decisiveness = short_ratio * 0.6 + confirm_ratio * 0.4
        return min(1.0, decisiveness)

    def _analyze_conflict_style(self, history: List[Tuple[str, str]]) -> str:
        """
        分析冲突解决风格
        """
        user_messages = [msg[1] for msg in history if msg[0] == "user"]
        combined = " ".join(user_messages)

        integrative_words = ["综合", "融合", "结合", "共识", "共同", "平衡", "兼顾"]
        competitive_words = ["不对", "错误", "我坚持", "反驳", "质疑", "反对"]
        avoidant_words = ["跳过", "忽略", "算了", "不管", "别说了", "先放着"]

        i_count = sum(1 for w in integrative_words if w in combined)
        c_count = sum(1 for w in competitive_words if w in combined)
        a_count = sum(1 for w in avoidant_words if w in combined)

        if i_count >= c_count and i_count >= a_count:
            return "integrative"
        elif c_count >= i_count and c_count >= a_count:
            return "competitive"
        else:
            return "avoidant"

    def _analyze_attention(self, history: List[Tuple[str, str]]) -> float:
        """
        分析注意力持续度
        通过对话长度和主题一致性判断
        """
        user_messages = [msg[1] for msg in history if msg[0] == "user"]
        if len(user_messages) < 3:
            return 0.5

        avg_length = sum(len(msg) for msg in user_messages) / len(user_messages)
        length_score = min(1.0, avg_length / 100)

        if len(user_messages) >= 5:
            first_words = set(user_messages[0][:50].split())
            recent_words = set(user_messages[-1][:50].split())
            common = len(first_words & recent_words) / max(1, len(first_words))
            consistency_score = common
        else:
            consistency_score = 0.5

        return length_score * 0.5 + consistency_score * 0.5

    def _analyze_thinking_style(self, history: List[Tuple[str, str]]) -> Dict[str, str]:
        """
        分析用户的思考风格（推理方式、类比偏好、输出风格）
        返回：{"reasoning_style": str, "analogy_preference": str, "output_style": str}
        """
        user_messages = [msg[1] for msg in history if msg[0] == "user"]
        if not user_messages:
            return {"reasoning_style": "balanced", "analogy_preference": "balanced", "output_style": "balanced"}

        combined = " ".join(user_messages)

        # 1. 推理风格：演绎 vs 归纳
        deductive_keywords = ["因为", "所以", "因此", "推导", "必然", "逻辑", "一般", "普遍", "所有"]
        inductive_keywords = ["比如", "例如", "具体", "案例", "观察", "发现", "数据", "实验", "实际"]

        deductive_score = sum(1 for kw in deductive_keywords if kw in combined)
        inductive_score = sum(1 for kw in inductive_keywords if kw in combined)

        if deductive_score > inductive_score * 1.5:
            reasoning_style = "deductive"
        elif inductive_score > deductive_score * 1.5:
            reasoning_style = "inductive"
        else:
            reasoning_style = "balanced"

        # 2. 类比偏好：类比 vs 第一性原理
        analogy_keywords = ["像", "如同", "好比", "类比", "相似", "比喻", "参考", "类似"]
        first_principles_keywords = ["本质", "底层", "根本", "源头", "基础", "原理", "原始", "基本"]

        analogy_score = sum(1 for kw in analogy_keywords if kw in combined)
        first_score = sum(1 for kw in first_principles_keywords if kw in combined)

        if analogy_score > first_score * 1.5:
            analogy_preference = "analogy"
        elif first_score > analogy_score * 1.5:
            analogy_preference = "first_principles"
        else:
            analogy_preference = "balanced"

        # 3. 输出风格：结论先行 vs 证据先行
        conclusion_first_keywords = ["总之", "结论", "总结", "概括", "核心", "关键是", "最终"]
        evidence_first_keywords = ["首先", "步骤", "依据", "数据", "证据", "我们观察到", "研究表明"]

        cf_score = sum(1 for kw in conclusion_first_keywords if kw in combined)
        ef_score = sum(1 for kw in evidence_first_keywords if kw in combined)

        if cf_score > ef_score * 1.5:
            output_style = "conclusion_first"
        elif ef_score > cf_score * 1.5:
            output_style = "evidence_first"
        else:
            output_style = "balanced"

        return {
            "reasoning_style": reasoning_style,
            "analogy_preference": analogy_preference,
            "output_style": output_style
        }

    def _analyze_language_style(self, history: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        分析用户的语言风格偏好
        """
        user_messages = [msg[1] for msg in history if msg[0] == "user"]
        combined = " ".join(user_messages)

        if len(user_messages) < 3:
            return {
                "wenbai_ratio": "balanced",
                "metaphor_preference": "balanced",
                "rhythm_preference": "balanced",
                "cultural_roots": ["儒家", "道家"]
            }

        # 1. 文白比例
        wen_markers = ["之", "乎", "者", "也", "矣", "焉", "哉", "兮", "其", "乃", "于", "以", "因", "故", "然", "则"]
        bai_markers = ["的", "了", "呢", "啊", "吧", "吗", "啦", "哟", "哦", "嗯", "哈", "嘿", "哎"]

        wen_count = sum(1 for w in wen_markers if w in combined)
        bai_count = sum(1 for w in bai_markers if w in combined)

        if wen_count > bai_count * 2:
            wenbai_ratio = "wen"
        elif bai_count > wen_count * 2:
            wenbai_ratio = "bai"
        else:
            wenbai_ratio = "balanced"

        # 2. 隐喻偏好
        nature_metaphors = ["山", "水", "月", "竹", "云", "风", "雨", "雪", "花", "树", "林", "江", "河", "湖", "海"]
        architecture_metaphors = ["楼", "台", "阁", "塔", "亭", "桥", "门", "墙", "城", "殿", "堂", "柱", "梁", "瓦", "砖"]
        military_metaphors = ["兵", "将", "帅", "军", "战", "阵", "营", "旗", "鼓", "剑", "刀", "弓", "箭", "骑", "马"]

        nature_score = sum(1 for w in nature_metaphors if w in combined)
        arch_score = sum(1 for w in architecture_metaphors if w in combined)
        military_score = sum(1 for w in military_metaphors if w in combined)

        if nature_score >= arch_score and nature_score >= military_score:
            metaphor_preference = "nature"
        elif arch_score >= nature_score and arch_score >= military_score:
            metaphor_preference = "architecture"
        elif military_score > 0:
            metaphor_preference = "military"
        else:
            metaphor_preference = "balanced"

        # 3. 节奏偏好
        long_sentences = [s for s in re.split(r'[，。！？；、]', combined) if len(s) > 20]
        short_sentences = [s for s in re.split(r'[，。！？；、]', combined) if 0 < len(s) <= 10]

        if len(long_sentences) > len(short_sentences) * 2:
            rhythm_preference = "long"
        elif len(short_sentences) > len(long_sentences) * 2:
            rhythm_preference = "short"
        else:
            rhythm_preference = "balanced"

        # 4. 文化根基（基于关键词检测）
        cultural_roots = []
        confucian_keywords = ["仁", "义", "礼", "智", "信", "中庸", "君子", "圣人", "孔", "孟", "儒家", "论语"]
        daoist_keywords = ["道", "德", "无为", "自然", "天人合一", "老子", "庄子", "道家", "逍遥", "齐物"]
        zen_keywords = ["禅", "空", "寂", "静", "悟", "心", "无念", "禅宗", "菩提", "明镜"]

        if any(kw in combined for kw in confucian_keywords):
            cultural_roots.append("儒家")
        if any(kw in combined for kw in daoist_keywords):
            cultural_roots.append("道家")
        if any(kw in combined for kw in zen_keywords):
            cultural_roots.append("禅宗")

        if not cultural_roots:
            cultural_roots = ["儒家", "道家"]  # 默认

        return {
            "wenbai_ratio": wenbai_ratio,
            "metaphor_preference": metaphor_preference,
            "rhythm_preference": rhythm_preference,
            "cultural_roots": cultural_roots[:3]
        }

    def get_cognitive_operators(self, fingerprint: CognitiveFingerprint) -> str:
        """生成用户专属认知操作符描述"""
        style_map = {
            "deductive": "演绎推理（从一般到特殊）",
            "inductive": "归纳推理（从特殊到一般）",
            "balanced": "演绎与归纳并重"
        }
        analogy_map = {
            "analogy": "类比思维（用已知解释未知）",
            "first_principles": "第一性原理（回归本质）",
            "balanced": "类比与本质分析并重"
        }
        output_map = {
            "conclusion_first": "先结论后展开",
            "evidence_first": "先证据后结论",
            "balanced": "结论与证据交替"
        }
        ops = [
            f"[思维模式：{style_map.get(fingerprint.reasoning_style, '平衡')}]",
            f"[论证偏好：{analogy_map.get(fingerprint.analogy_preference, '平衡')}]",
            f"[输出偏好：{output_map.get(fingerprint.output_style, '平衡')}]"
        ]
        return " ".join(ops)

    def get_language_style_description(self, fingerprint: CognitiveFingerprint) -> str:
        """生成用户专属语言风格描述"""
        lang = fingerprint.language_style

        wenbai_map = {
            "wen": "文言语感（典雅庄重）",
            "bai": "白话风格（亲切自然）",
            "balanced": "文白相间（从容有度）"
        }

        metaphor_map = {
            "nature": "山水自然意象（如月、竹、云、水）",
            "architecture": "建筑空间意象（如楼、台、亭、阁）",
            "military": "兵家意象（如棋、阵、剑、策）",
            "balanced": "自然与人文意象并重"
        }

        rhythm_map = {
            "short": "短句快节奏（如疾风骤雨）",
            "long": "长句慢节奏（如大江大河）",
            "balanced": "长短句相间（如行云流水）"
        }

        roots = "、".join(lang.get("cultural_roots", ["儒家", "道家"]))

        return f"[语言风格：{wenbai_map.get(lang.get('wenbai_ratio', 'balanced'), '文白相间')}] " \
               f"[隐喻偏好：{metaphor_map.get(lang.get('metaphor_preference', 'balanced'), '自然意象')}] " \
               f"[节奏：{rhythm_map.get(lang.get('rhythm_preference', 'balanced'), '长短相间')}] " \
               f"[文化根基：{roots}]"

    def _smooth_update(self, old_val: float, new_val: float, factor: float = 0.3) -> float:
        """平滑更新，防止指纹突变"""
        if old_val is None:
            return new_val
        return old_val * (1 - factor) + new_val * factor

    def _merge_role_history(self, old: Dict[str, int], new: Dict[str, int]) -> Dict[str, int]:
        """合并角色历史"""
        merged = old.copy()
        for role, count in new.items():
            merged[role] = merged.get(role, 0) + int(count)
        return merged

    def _build_evolution_log(self, old: CognitiveFingerprint, new: CognitiveFingerprint) -> List[Dict[str, Any]]:
        """构建演化日志"""
        changes = []
        if abs(old.risk_tolerance - new.risk_tolerance) > 0.1:
            changes.append({
                "dimension": "risk_tolerance",
                "old": old.risk_tolerance,
                "new": new.risk_tolerance
            })
        if abs(old.innovation_preference - new.innovation_preference) > 0.1:
            changes.append({
                "dimension": "innovation_preference",
                "old": old.innovation_preference,
                "new": new.innovation_preference
            })
        if abs(old.decisiveness - new.decisiveness) > 0.1:
            changes.append({
                "dimension": "decisiveness",
                "old": old.decisiveness,
                "new": new.decisiveness
            })
        if old.preferred_role != new.preferred_role:
            changes.append({
                "dimension": "preferred_role",
                "old": old.preferred_role,
                "new": new.preferred_role
            })

        old_logs = old.evolution_log[-15:] if old.evolution_log else []
        return old_logs + [{
            "timestamp": datetime.now().isoformat(),
            "changes": changes,
            "total_interactions": new.total_interactions
        }]

    def _save_fingerprint(self, fingerprint: CognitiveFingerprint) -> None:
        """保存认知指纹到文件"""
        data = {
            "fingerprint": fingerprint.to_dict(),
            "extraction_metadata": {
                "last_extraction": datetime.now().isoformat(),
                "messages_analyzed": fingerprint.total_interactions,
                "debates_analyzed": 0,
                "crystals_created": 0,
                "version": "1.0"
            }
        }
        self.files.write_fingerprint(data)

    def get_fingerprint(self) -> CognitiveFingerprint:
        """获取当前认知指纹"""
        data = self.files.read_fingerprint()
        return CognitiveFingerprint.from_dict(data.get("fingerprint", {}))
