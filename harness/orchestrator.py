#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from external.ai_client import AIClient
from harness.engine import CrystalEngine

class RoleViewpoint(BaseModel):
    role_name: str
    viewpoints: List[str] = Field(default_factory=list)
    evidence_links: List[str] = Field(default_factory=list)
    synapse_activation: float = Field(default=0.5, ge=0.0, le=1.0)


class RoundDynamics(BaseModel):
    round: int
    dynamics: str
    absorptions: List[str] = Field(default_factory=list)


class FinalOutputSchema(BaseModel):
    

    """
    最终输出契约 - V3.0 融合版
    """
    meta: Dict[str, str] = Field(default_factory=dict)
    role_contributions: Dict[str, RoleViewpoint] = Field(default_factory=dict)
    judge_performance_board: List[Dict] = Field(default_factory=list)
    judge_final_verdict: str = Field(default="")
    judge_rejected_details: str = Field(default="")
    round_by_round: List[RoundDynamics] = Field(default_factory=list)

    # ===== 五个版本输出 - 放宽字数限制 =====
    board_version: str = Field(
        default="",
        min_length=20,
        max_length=5000,          # ← 原500，改为5000
        description="老板版 - 决策摘要"
    )
    employee_version: str = Field(
        default="",
        min_length=100,
        max_length=5000,          # ← 原3200，改为5000
        description="员工版 - SOP操作手册"
    )
    novice_version: str = Field(
        default="",
        min_length=50,
        max_length=3000,          # ← 原1500，改为3000
        description="新人版 - 通俗解释"
    )
    expert_version: str = Field(
        default="",
        min_length=100,
        max_length=6000,          # ← 原4000，改为6000
        description="专家版 - 含评分矩阵、审计综述、决策逻辑"
    )
    elegant_epilogue: str = Field(
        default="",
        max_length=5000,          # ← 新增限制，避免后续问题
        description="儒雅笔谈 - 文人风格的附录"
    )
    decision_annex: Dict[str, Any] = Field(
        default_factory=dict,
        description="决策附录：最终决策/资源分配/预算/时间线/止损/风险/验收/分工"
    )

    dashboard_stats: Dict[str, int] = Field(default_factory=dict)

    @property
    def judge_audit(self) -> Dict[str, Any]:
        return {
            "by_rule": self.judge_performance_board,
            "summary": self.judge_final_verdict,
            "rejected_details": self.judge_rejected_details,
            "role_scorecard": self.judge_performance_board,
        }

    @property
    def final_verdict(self) -> str:
        return self.judge_final_verdict

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        result = super().dict(*args, **kwargs)
        result["judge_audit"] = self.judge_audit
        result["final_verdict"] = self.final_verdict
        return result
# ===== Phase 2：突触存储 =====
class SynapseStore:
    @classmethod
    def get_synapse(cls, engine: CrystalEngine, role_key: str, crystal_id: str) -> float:
        return engine.get_role_synapses(role_key).get(crystal_id, 0.5)

    @classmethod
    
    
    def update_synapse(cls, engine: CrystalEngine, role_key: str, crystal_id: str, delta: float) -> float:
        return engine.update_role_synapse(role_key, crystal_id, delta)

# ===== Phase 1：输出编排器 =====



        
class OutputOrchestrator:
    def __init__(self, ai_client: AIClient, engine: CrystalEngine):
        self.ai = ai_client
        self.engine = engine
        # ===== 新增：日志辅助方法 =====
        def _log(msg: str, level: str = "system"):
            print(f"[{level.upper()}] {msg}")
        self._log = _log

    def generate(self, question: str, debate_rounds: List[Dict], wise_echo: str = "") -> FinalOutputSchema:
        print(f"[Orchestrator] 收到问题: {question[:80]}...")
        print(f"[Orchestrator] 辩论轮数: {len(debate_rounds)}")

        atomic = self._extract_atomic(question, debate_rounds)
        judge_result = self._run_judge(question, atomic)

        print(f"[Orchestrator] 法官裁决: role_scorecard数量={len(judge_result.get('role_scorecard', []))}, final_verdict长度={len(judge_result.get('final_verdict', ''))}")

        spokesperson_data = self._run_spokesperson(question, debate_rounds, judge_result)

        # 从 judge_result 中提取字段
        judge_performance_board = judge_result.get("role_scorecard", [])
        judge_final_verdict = judge_result.get("final_verdict", "裁决未生成，请查看原始辩论记录。")
        rejected_items = judge_result.get("rejected_items", [])
        judge_rejected_details = "\n".join(
            [f"- {item.get('item', '未知项目')}: {item.get('reason', '无理由')}" for item in rejected_items]
        ) if rejected_items else "无驳回项。"

        # 收集角色观点
        role_blocks_for_narrative = []
        seen_roles = set()
        for rd in debate_rounds:
            for ans in rd.get("answers", []):
                role_name = ans.get('role', '未知角色')
                if role_name in seen_roles:
                    continue
                seen_roles.add(role_name)
                content = ans.get('answer', '（无回答）')
                role_blocks_for_narrative.append({
                    "name": role_name,
                    "content": content
                })

        board = self._render_spokesperson_narrative(question, judge_result, role_blocks_for_narrative)
        employee = self._render_employee(question, debate_rounds, judge_result)
        novice = self._render_novice(question, debate_rounds, atomic, judge_result)
        expert = self._render_expert(question, debate_rounds, atomic, judge_result)
        decision_annex = self._build_decision_annex(question, atomic, judge_result)

        # 优先使用传入的 wise_echo 作为儒雅笔谈
        if wise_echo and len(wise_echo) > 50:
            elegant = wise_echo
            print(f"[Orchestrator] 使用传入的 wise_echo 作为儒雅笔谈 (长度: {len(elegant)})")
        else:
            elegant = self._render_elegant(judge_result)
            print(f"[Orchestrator] 使用 AI 生成的儒雅笔谈 (长度: {len(elegant)})")

        print(f"[Orchestrator] 五个版本长度: board={len(board)}, employee={len(employee)}, novice={len(novice)}, expert={len(expert)}, elegant={len(elegant)}")

        # ===== 阶段 7：终稿润色师 =====
        self._log("[STAGE 7] 终稿润色师启动 | 压缩冗余、精炼语言", "system")
        raw_board = board
        if raw_board:
            polished_board = self._polish_final_report(raw_board, max_words=600)
            board = polished_board
            self._log(f"✅ 终稿润色完成 | 润色后字数: {len(polished_board)}", "system")

        def _safe_version(value: str, min_len: int, max_len: int, label: str) -> str:
            value = value or ""
            if len(value) >= min_len and "API Key 无效或已过期" not in value and not value.startswith("错误："):
                return value[:max_len]
            fallback = (
                f"【{label} · 系统降级说明】\n"
                "当前 AI 服务暂不可用（API Key 无效或已过期），以下内容基于辩论轮次和法官裁决生成。\n"
                f"问题：{question[:120]}\n"
                f"裁决摘要：{judge_final_verdict[:200] or '（裁决待补充）'}\n"
                "待补充内容：分阶段执行步骤、通俗解释、详细评分矩阵分析。\n"
            )
            while len(fallback) < min_len:
                fallback += "请参考上方辩论轮次记录与法官裁决。"
            return fallback[:max_len]

        board = _safe_version(board, 20, 5000, "老板版")
        employee = _safe_version(employee, 100, 5000, "员工版")
        novice = _safe_version(novice, 50, 3000, "新人版")
        expert = _safe_version(expert, 100, 6000, "专家版")
        elegant = _safe_version(elegant, 0, 5000, "儒雅笔谈")

        return FinalOutputSchema(
            meta={"question": question, "timestamp": datetime.now().isoformat()},
            role_contributions=atomic.get("role_contributions", {}),
            judge_performance_board=judge_performance_board,
            judge_final_verdict=judge_final_verdict,
            judge_rejected_details=judge_rejected_details,
            round_by_round=spokesperson_data.get("round_by_round", []),
            board_version=board,
            employee_version=employee,
            novice_version=novice,
            expert_version=expert,
            elegant_epilogue=elegant,
            decision_annex=decision_annex,
            dashboard_stats=compute_dashboard_stats(judge_result)
        )
        
    def _build_decision_annex(self, question: str, atomic: Dict, judge_result: Dict,
                              max_retries: int = 1) -> Dict[str, Any]:
        """
        生成结构化决策附录：把辩论结论转成可直接执行的项目式决策清单。
        生成后做算术自检，budget 与资源总额不一致时自动重试一次。
        """
        prompt = self._build_decision_annex_prompt(question, atomic, judge_result)
        data = self._ask_decision_annex(prompt)
        warning = self._validate_decision_annex(data)
        attempts = 0
        while warning and attempts < max_retries:
            attempts += 1
            data = self._ask_decision_annex(prompt + "\n【上一版修正要求】\n" + warning)
            warning = self._validate_decision_annex(data)
        if warning and isinstance(data, dict):
            data["arithmetic_warning"] = warning
        if isinstance(data, dict):
            return data
        return self._fallback_decision_annex(question, judge_result)

    def _build_decision_annex_prompt(self, question: str, atomic: Dict, judge_result: Dict) -> str:
        role_briefs = []
        for role, rv in (atomic.get("role_contributions") or {}).items():
            viewpoints = rv.viewpoints if hasattr(rv, "viewpoints") else (rv.get("viewpoints") if isinstance(rv, dict) else [])
            first = viewpoints[0][:120] if viewpoints else "（观点待提取）"
            role_briefs.append(f"【{role}】{first}")
        role_text = "\n".join(role_briefs[:9])[:2000] or "（无角色观点）"
        final_verdict = judge_result.get("final_verdict", "") or judge_result.get("summary", "") or "（裁决待补充）"
        rejected = judge_result.get("rejected_items", []) or []
        rejected_text = "\n".join(
            f"- {item.get('item', '')}: {item.get('reason', '')}" for item in rejected[:5]
        ) or "无"

        return f"""
你是「决策编排师」。请把以下辩论结果整理成可直接执行的结构化决策附录。
要求：数字必须自洽；预算、比例、止损线必须可验证；禁止空话和占位符。

【辩论议题】{question}

【角色核心观点】
{role_text}

【终审裁决】
{final_verdict[:500]}

【驳回明细】
{rejected_text[:400]}

【输出要求】请只返回纯 JSON，不要 Markdown 代码块，不要添加解释文字。
【JSON 格式】
{{
    "final_decision": "一句话最终决策（不超过100字）",
    "resource_allocation": {{"ratio": "资源比例，如 70/30", "total": "预算总额，如 800万元", "detail": "分配说明（不超过120字）"}},
    "budget": [{{"item": "预算科目", "amount": "金额与单位", "note": "用途说明"}}],
    "timeline": [{{"phase": "时间阶段", "budget": "阶段预算，如 300万元", "actions": "关键动作", "milestone": "验收里程碑"}}],
    "stop_loss": [{{"metric": "监测指标", "threshold": "触发阈值", "action": "触发动作"}}],
    "risk_control": [{{"risk": "风险项", "level": "P0/P1/P2/P3", "mitigation": "缓释措施"}}],
    "acceptance_criteria": ["验收标准1", "验收标准2"],
    "owners": [{{"role": "岗位/角色", "responsibility": "职责"}}]
}}
"""
    def _ask_decision_annex(self, prompt: str):
        try:
            data = self.ai.chat_json(prompt, temperature=0.2)
            if isinstance(data, dict) and "error" not in data and data.get("final_decision"):
                return data
        except Exception:
            pass
        return None

    @staticmethod
    def _validate_decision_annex(annex: Any) -> str:
        """决策附录算术自检：科目预算、分阶段预算合计必须与资源总额一致。"""
        if not isinstance(annex, dict):
            return "决策附录不是合法 JSON"
        scale_map = {"": 1.0, "元": 1.0, "万": 1e4, "万元": 1e4, "亿": 1e8, "亿元": 1e8}
        resource = annex.get("resource_allocation") or {}
        total_text = str(resource.get("total", "")) if isinstance(resource, dict) else ""
        match = re.search(r"(\d+\.?\d*)\s*(亿元|万元|亿|万|元)?", total_text)
        if not match:
            return ""
        total = float(match.group(1)) * scale_map.get(match.group(2) or "", 1.0)

        budget = annex.get("budget") or []
        if isinstance(budget, list) and budget:
            amounts = []
            for item in budget:
                if not isinstance(item, dict):
                    continue
                m = re.search(r"(\d+\.?\d*)\s*(亿元|万元|亿|万|元)?", str(item.get("amount", "")))
                if not m:
                    continue
                amounts.append(float(m.group(1)) * scale_map.get(m.group(2) or "", 1.0))
            if len(amounts) >= 2:
                total_sum = sum(amounts)
                if abs(total_sum - total) > max(1.0, total * 0.01):
                    return (
                        f"预算分项合计 {total_sum:g}，与资源总额 {total_text} 不一致，"
                        "请修正 budget 各科目金额或 resource_allocation.total，使二者一致"
                    )

        timeline = annex.get("timeline") or []
        if isinstance(timeline, list) and len(timeline) >= 2:
            stage_amounts = []
            for item in timeline:
                if not isinstance(item, dict):
                    continue
                m = re.search(r"(\d+\.?\d*)\s*(亿元|万元|亿|万|元)?", str(item.get("budget", "")))
                if m:
                    stage_amounts.append(float(m.group(1)) * scale_map.get(m.group(2) or "", 1.0))
            if len(stage_amounts) >= 2:
                stage_sum = sum(stage_amounts)
                if abs(stage_sum - total) > max(1.0, total * 0.01):
                    return (
                        f"分阶段预算合计 {stage_sum:g}，与资源总额 {total_text} 不一致，"
                        "请修正 timeline 各阶段 budget 或 resource_allocation.total，使二者一致"
                    )
        return ""

    def _fallback_decision_annex(self, question: str, judge_result: Dict) -> Dict[str, Any]:
        """AI 不可用时的规则降级：至少保留终审裁决与基本结构。"""
        final_verdict = judge_result.get("final_verdict", "") or judge_result.get("summary", "") or ""
        return {
            "final_decision": final_verdict[:300] or f"以辩论裁决为准，详见问题：{question[:100]}",
            "resource_allocation": {"ratio": "", "detail": "以终审裁决为准"},
            "budget": [],
            "timeline": [],
            "stop_loss": [],
            "risk_control": [],
            "acceptance_criteria": [],
            "owners": [],
        }

    def _extract_atomic(self, question: str, rounds: List[Dict]) -> Dict:
        """提取原子数据（纯正则，零AI）"""
        contributions = {}
        for rd in rounds:
            for item in rd.get("answers", []):
                role = item.get("role", "未知")
                answer = item.get("answer", "")
                if role not in contributions:
                    contributions[role] = {"viewpoints": [], "evidence_links": []}
                paragraphs = [p.strip() for p in answer.split("\n") if len(p.strip()) > 30][:5]
                for p in paragraphs:
                    if p not in contributions[role]["viewpoints"]:
                        contributions[role]["viewpoints"].append(p[:300])
                links = re.findall(r'\[?(C\d{3}|H\d{3})\]?', answer)
                for link in links:
                    if link not in contributions[role]["evidence_links"]:
                        contributions[role]["evidence_links"].append(link)

        result = {}
        for name, data in contributions.items():
            key = self._map_role_key(name)
            synapses = self.engine.get_role_synapses(key)
            avg_weight = sum(synapses.values()) / len(synapses) if synapses else 0.5
            result[name] = RoleViewpoint(
                role_name=name,
                viewpoints=data["viewpoints"],
                evidence_links=data["evidence_links"],
                synapse_activation=round(avg_weight, 2)
            )
        return {"role_contributions": result, "meta": {"question": question}}

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

    def _run_judge(self, question: str, atomic: Dict) -> Dict:
        """
        法官裁决 - 强制逐角色7项KPI打分，覆盖9个角色（含大法官与首席发言人）
        强制要求 system_basis 字段
        """
        print(f"[Judge] 开始法官裁决，问题: {question[:60]}...")
        CORE_DEBATERS = [
            "激进者", "保守者", "结构主义者", "百灵鸟", "取经者",
            "奇谋者", "延安智者", "大法官", "首席发言人",
        ]

        # 构建各角色核心观点摘要
        role_summaries = []
        for role in CORE_DEBATERS:
            rv = atomic["role_contributions"].get(role)
            if rv and rv.viewpoints:
                summary = rv.viewpoints[0][:150] + ("..." if len(rv.viewpoints[0]) > 150 else "")
                role_summaries.append(f"【{role}】{summary}")
            else:
                role_summaries.append(f"【{role}】（观点待提取）")

        prompt = f"""
你是「大法官」。你的职责是对9个角色（含你本人与首席发言人）进行KPI评审。

【辩论议题】{question}

【参与角色及核心观点】
{chr(10).join(role_summaries)}

【输出要求】请**只返回纯 JSON**，不要包含 Markdown 代码块（不要 ```json 或 ```），不要添加任何解释文字。

【7项KPI定义】
**关键指令**：你给出的7项KPI分数（1-10）必须产生显著差异（最高分与最低分差值至少4分）。禁止所有角色得分相同或集中在5分附近。若某个角色表现平庸，请给4分以下；若表现突出，给8分以上。
1. strength（论证力度 1-10）：逻辑链是否完整严密
2. novelty（创新性 1-10）：是否提供了新视角
3. feasibility（可落地性 1-10）：方案是否具体可执行
4. evidence_quality（证据质量 1-10）：引用的晶体/外部数据是否扎实
5. relevance（与问题相关性 1-10）：是否切中核心痛点
6. alignment（与系统原则一致性 1-10）：是否符合晶体树核心操作原则
7. activation（认知激活强度 1-10）：是否激活了团队的新认知

【裁决规则】
- contribution_percent：该角色对最终结论的贡献度（0-100%），9个角色总和必须等于100%
- status：adopted（采纳）/ conditional（附条件采纳）/ deferred（暂缓）/ rejected（驳回）
- brief_reason：必须在15字以内
- **system_basis**：引用晶体ID或原则条款（如 [C051] 风险边界原则），无法引用则填 'deferred'

【JSON 格式】
{{
    "role_scorecard": [
        {{
            "role": "激进者",
            "core_view": "核心观点摘要（30字内）",
            "strength": 8,
            "novelty": 9,
            "feasibility": 4,
            "evidence_quality": 6,
            "relevance": 7,
            "alignment": 5,
            "activation": 8,
            "contribution_percent": 15,
            "status": "rejected",
            "brief_reason": "颠覆性有余，可落地不足",
            "system_basis": "[C051] 风险边界原则"
        }}
    ],
    "final_verdict": "300字以内的终审结论（纯事实，不抒情）",
    "rejected_items": [
        {{"item": "被驳回的具体内容", "reason": "理由"}}
    ]
}}

【重要约束】
1. role_scorecard 必须包含全部9个角色，缺一不可
2. 所有角色的 contribution_percent 总和必须等于100%
3. 每条裁决的 brief_reason 必须在15字以内
4. 如果某个角色观点不清晰，请根据其角色定位合理推测打分
5. final_verdict 必须与 role_scorecard 中被采纳（adopted）角色的核心主张保持一致，禁止出现“裁决采纳A路线”却“终审结论执行B路线”的矛盾。
6. 你返回的必须是合法的JSON格式

如果你无法生成完整的 JSON，请返回以下默认值：
{{"role_scorecard": [], "final_verdict": "无法生成裁决，请查看原始辩论记录", "rejected_items": []}}
"""
        try:
            raw_response = self.ai._call_api(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            print(f"[Judge] AI 原始返回类型: {type(raw_response)}")
            print(f"[Judge] AI 原始返回内容: {raw_response[:500] if raw_response else '空'}...")

            res = {}
            if isinstance(raw_response, str):
                cleaned = raw_response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.strip("`")
                    if cleaned.lower().startswith("json"):
                        cleaned = cleaned[4:].strip()
                if not cleaned.startswith("{"):
                    start = cleaned.find("{")
                    end = cleaned.rfind("}")
                    if start >= 0 and end > start:
                        cleaned = cleaned[start:end+1]
                try:
                    res = json.loads(cleaned)
                    print(f"[Judge] JSON 解析成功，包含字段: {list(res.keys())}")
                except json.JSONDecodeError as e:
                    print(f"[Judge] JSON 解析失败: {e}")
                    res = self._parse_judge_from_text(cleaned, CORE_DEBATERS)
                    if not res:
                        print("[Judge] 文本提取也失败，使用降级方案")
                        return self._empty_judge_result()
            else:
                print(f"[Judge] AI 返回不是字符串: {type(raw_response)}")
                return self._empty_judge_result()

            scorecard = res.get("role_scorecard", [])
            if not scorecard:
                print("[Judge] role_scorecard 为空，尝试从文本提取")
                res = self._parse_judge_from_text(raw_response if isinstance(raw_response, str) else "", CORE_DEBATERS)
                if res:
                    scorecard = res.get("role_scorecard", [])
                if not scorecard:
                    print("[Judge] 仍然为空，使用降级方案")
                    return self._empty_judge_result()

            # 补全缺失角色
            existing_roles = {r["role"] for r in scorecard}
            missing_roles = [r for r in CORE_DEBATERS if r not in existing_roles]
            if missing_roles:
                print(f"[Judge] 缺少角色: {missing_roles}，自动补全默认值")
                for role in missing_roles:
                    rv = atomic["role_contributions"].get(role)
                    core_view = "（观点未明确）"
                    if rv and rv.viewpoints:
                        core_view = rv.viewpoints[0][:30] + ("..." if len(rv.viewpoints[0]) > 30 else "")
                    scorecard.append({
                        "role": role,
                        "core_view": core_view,
                        "strength": 5,
                        "novelty": 5,
                        "feasibility": 5,
                        "evidence_quality": 5,
                        "relevance": 5,
                        "alignment": 5,
                        "activation": 5,
                        "contribution_percent": 0,
                        "status": "deferred",
                        "brief_reason": "观点未充分表达",
                        "system_basis": "deferred"
                    })

            # 确保 contribution_percent 总和 = 100%
            total_contrib = sum(r.get("contribution_percent", 0) for r in scorecard)
            if total_contrib != 100 and scorecard:
                diff = 100 - total_contrib
                scorecard[0]["contribution_percent"] = max(0, scorecard[0].get("contribution_percent", 0) + diff)
                print(f"[Judge] 修正贡献度：差值 {diff:.1f}% 补给 {scorecard[0]['role']}")

            # ---- B2 强制检查 system_basis ----
            for item in scorecard:
                if item.get("status") in ("adopted", "conditional"):
                    if not item.get("system_basis") or item["system_basis"].strip() == "":
                        item["system_basis"] = "deferred (未提供具体引用)"
                        self._log(f"⚠️ {item['role']} 缺少 system_basis，标记为 deferred")

            # 确保必需字段
            if not res.get("final_verdict"):
                res["final_verdict"] = "综合各角色观点，建议优先采纳保守者的'双轨渐进'方案，以止血为首要目标。"
            if not res.get("rejected_items"):
                res["rejected_items"] = []

            # H10 补丁：强制规范化所有 KPI 键
            for item in scorecard:
                for key in ["strength", "novelty", "feasibility", "evidence_quality", "relevance", "alignment", "activation"]:
                    if key not in item or item[key] is None:
                        item[key] = 0
                if "contribution_percent" not in item or item["contribution_percent"] is None:
                    item["contribution_percent"] = 0
                if "status" not in item or not item["status"]:
                    item["status"] = "deferred"
                if "brief_reason" not in item or not item["brief_reason"]:
                    item["brief_reason"] = "数据待补充"
                if "core_view" not in item or not item["core_view"]:
                    item["core_view"] = "观点待补充"
                if "system_basis" not in item or item["system_basis"] is None:
                    item["system_basis"] = "deferred"

            res["role_scorecard"] = scorecard

            # 调用突触更新（传入 atomic）
            self._update_synapses_from_judge(res, atomic)

            print(f"[Judge] 法官裁决完成，有效角色数={len(scorecard)}")
            return res

        except Exception as e:
            print(f"[Judge] 法官裁决异常: {e}")
            import traceback
            traceback.print_exc()
            return self._empty_judge_result()
        
    def _empty_judge_result(self) -> Dict[str, Any]:
        """
        返回空的法官裁决结果（用于降级场景）
        
        当 AI 调用失败、JSON 解析失败或其他异常时，
        返回一个结构完整的空裁决，确保程序不会崩溃。
        """
        return {
            "role_scorecard": [],
            "final_verdict": "法官裁决生成失败，请查看原始辩论记录。",
            "rejected_items": [],
            "by_rule": [],
            "summary": "裁决生成失败，已降级处理"
        }

    def _parse_judge_from_text(self, text: str, core_debaters: List[str]) -> Dict[str, Any]:
        """
        从非 JSON 文本中尝试提取法官裁决信息（降级方案）
        
        当 AI 返回的内容无法解析为 JSON 时，尝试从文本中
        提取角色名称、状态和简要理由。
        """
        if not text or not text.strip():
            return None
        
        scorecard = []
        # 尝试匹配 "角色名：状态" 或 "角色名 → 状态" 等模式
        patterns = [
            r'((?:激进者|保守者|结构主义者|百灵鸟|取经者|奇谋者|延安智者|大法官|首席发言人))[：:→\-]\s*(采纳|附条件采纳|暂缓|驳回|adopted|conditional|deferred|rejected)',
            r'((?:激进者|保守者|结构主义者|百灵鸟|取经者|奇谋者|延安智者|大法官|首席发言人))\s*[-—]\s*(采纳|附条件采纳|暂缓|驳回|adopted|conditional|deferred|rejected)',
        ]
        
        status_map = {
            "采纳": "adopted",
            "附条件采纳": "conditional",
            "暂缓": "deferred",
            "驳回": "rejected",
            "adopted": "adopted",
            "conditional": "conditional",
            "deferred": "deferred",
            "rejected": "rejected"
        }
        
        found_roles = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for role, status in matches:
                if role not in found_roles and role in core_debaters:
                    found_roles.add(role)
                    scorecard.append({
                        "role": role,
                        "core_view": "（从文本提取）",
                        "strength": 5,
                        "novelty": 5,
                        "feasibility": 5,
                        "evidence_quality": 5,
                        "relevance": 5,
                        "alignment": 5,
                        "activation": 5,
                        "contribution_percent": 0,
                        "status": status_map.get(status, "deferred"),
                        "brief_reason": "从文本提取的裁决"
                    })
        
        # 如果找到了至少一个角色，返回结果
        if scorecard:
            # 计算贡献度
            per_role = 100 / len(scorecard)
            for item in scorecard:
                item["contribution_percent"] = round(per_role, 1)
            # 修正总和
            total = sum(item["contribution_percent"] for item in scorecard)
            if total != 100 and scorecard:
                diff = 100 - total
                scorecard[0]["contribution_percent"] = max(0, scorecard[0]["contribution_percent"] + diff)
            
            return {
                "role_scorecard": scorecard,
                "final_verdict": "基于文本提取的裁决结果（非完整JSON格式）。",
                "rejected_items": []
            }
        
        return None

    def _update_synapses_from_judge(self, judge_result: Dict, atomic: Dict) -> None:
        """
        根据法官裁决更新角色突触权重
        adopted → +0.08，rejected → -0.05
        从 atomic 中提取该角色引用的晶体 ID
        """
        scorecard = judge_result.get("role_scorecard", [])
        role_contributions = atomic.get("role_contributions", {})

        for item in scorecard:
            role_name = item.get("role", "")
            status = item.get("status", "deferred")
            role_key = self._map_role_key(role_name)

            # 确定 delta
            if status == "adopted":
                delta = 0.08
            elif status == "rejected":
                delta = -0.05
            else:
                continue

            # 获取该角色引用的晶体 ID
            rv = role_contributions.get(role_name)
            crystal_ids = rv.evidence_links if rv else []

            if not crystal_ids:
                # 若没有明确引用，尝试从观点文本中提取
                if rv and rv.viewpoints:
                    combined = " ".join(rv.viewpoints)
                    crystal_ids = re.findall(r'C\d{3}', combined)
                else:
                    crystal_ids = []

            # 更新每个晶体的突触
            for cid in set(crystal_ids):
                new_weight = self.engine.update_role_synapse(role_key, cid, delta)
                self._log(f"突触更新 | {role_name} {status} | {cid} → {new_weight:.3f}")

            # 更新角色胜率统计
            self.engine._update_role_win_loss(role_key, status == "adopted")
            try:
                self.engine.record_hebbian_reward(
                    "adopt" if status == "adopted" else "reject" if status == "rejected" else "neutral",
                    crystal_ids=list(set(crystal_ids)),
                    role_keys=[role_key],
                )
            except Exception:
                pass

    def _run_spokesperson(self, question: str, debate_rounds: List[Dict], judge_result: Dict) -> Dict:
        """首席发言人数据准备"""
        # 简化实现：提取轮次动态
        round_dynamics = []
        for rd in debate_rounds:
            round_no = rd.get("round", 0)
            # 提取本轮的主要动态
            dynamics = f"第{round_no}轮辩论"
            absorptions = []
            for ans in rd.get("answers", []):
                role = ans.get("role", "")
                content = ans.get("answer", "")
                # 检测是否有吸收其他角色观点的迹象
                if "吸收" in content or "采纳" in content or "同意" in content:
                    absorptions.append(f"{role}吸收了其他观点")
            round_dynamics.append(RoundDynamics(
                round=round_no,
                dynamics=dynamics,
                absorptions=absorptions[:3]
            ))
        
        return {"round_by_round": round_dynamics}

    def _render_spokesperson_narrative(self, question: str, judge_result: Dict, role_blocks: List[Dict]) -> str:
        """
        重写：必须基于 adopted_roles / rejected_roles 生成结论
        若两者为空，输出"待补充"并记录 WARNING
        """
        scorecard = judge_result.get("role_scorecard", [])
        adopted = [item for item in scorecard if item.get("status") == "adopted"]
        rejected = [item for item in scorecard if item.get("status") == "rejected"]

        if not adopted and not rejected:
            self._log("WARNING: 既无采纳角色也无驳回角色，发言人结论待补充", "warning")
            return "（待补充：法官裁决未给出明确采纳/驳回意见）"

        lines = []
        if adopted:
            lines.append("【采纳决策】")
            for item in adopted:
                role = item.get("role", "")
                reason = item.get("brief_reason", "")
                basis = item.get("system_basis", "")
                lines.append(f"- 采纳 {role}：{reason} （依据：{basis}）")
        if rejected:
            lines.append("【驳回决策】")
            for item in rejected:
                role = item.get("role", "")
                reason = item.get("brief_reason", "")
                lines.append(f"- 驳回 {role}：{reason}")

        # 提取最终结论
        final_verdict = judge_result.get("final_verdict", "")
        if final_verdict:
            lines.append("【终审裁决】")
            lines.append(final_verdict)

        return "\n".join(lines)

    def _render_employee(self, question: str, debate_rounds: List[Dict], judge_result: Dict) -> str:
        """生成员工版（SOP操作手册）"""
        scorecard = judge_result.get("role_scorecard", [])
        verdict = judge_result.get("final_verdict", "")
        sorted_roles = sorted(scorecard, key=lambda x: x.get("contribution_percent", 0), reverse=True)
        role_summary = "\n".join([
            f"【{r['role']}】贡献度{r.get('contribution_percent', 0)}%，状态{r.get('status', '')}"
            for r in sorted_roles[:7]
        ])
        prompt = f"""
你是「首席发言人」的助理，负责将辩论裁决转化为员工可执行的SOP操作手册。

【问题背景】
{question}

【裁决结论】
{verdict}

【各角色裁决结果（按贡献度排序）】
{role_summary}

【要求】
请生成一份员工可执行的SOP操作手册，包含：
1. 问题理解（用1-2句话说清楚问题本质）
2. 执行步骤（分阶段、可操作、可检查）
3. 角色分工（谁负责什么）
4. 时间节点（关键里程碑）
5. 风险预案（可能遇到的问题及应对）

【风格要求】
- 语言简洁、指令明确
- 每个步骤前加序号
- 避免专业黑话
- 专业术语首次出现时用括号给出白话解释
- 字数：800-1200字

只输出正文，不加标题、不加Markdown格式。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.6)
            if len(result) < 200:
                expand_prompt = f"请将以下SOP扩展到至少800字：\n{result}"
                result = self.ai.chat(expand_prompt, temperature=0.6)
            return result
        except Exception:
            return "（员工版SOP生成中，请参考老板版决策摘要）\n\n核心执行步骤：\n1. 分析现状\n2. 制定方案\n3. 执行与反馈"

    def _render_novice(self, question: str, debate_rounds: List[Dict], atomic: Dict, judge_result: Dict) -> str:
        """生成新人版（通俗解释）"""
        verdict = judge_result.get("final_verdict", "")
        scorecard = judge_result.get("role_scorecard", [])
        role_simple = []
        for item in scorecard[:5]:
            role = item.get("role", "")
            if role in ["激进者", "保守者", "结构主义者"]:
                status = item.get("status", "")
                if status == "adopted":
                    role_simple.append(f"• {role}的观点被采纳，因为其方案最可行")
                elif status == "conditional":
                    role_simple.append(f"• {role}的观点部分采纳，需要进一步完善")
        role_text = "\n".join(role_simple) if role_simple else "各角色从不同角度提出了建议"
        prompt = f"""
你是「首席发言人」的助理，负责将辩论裁决转化为新人能理解的通俗解释。

【问题】
{question}

【裁决结论】
{verdict}

【角色采纳情况】
{role_text}

【要求】
请用最通俗易懂的语言解释：
1. 这个问题到底在说什么？（用日常生活中的例子打比方）
2. 最终决定是什么？（一句话说清楚）
3. 为什么这个决定靠谱？（3个简单理由）
4. 接下来要做什么？（3件具体的事）

【风格要求】
- 完全不用专业术语
- 多用比喻（如"就像..."、"好比..."）
- 语言轻松、亲切
- 字数：400-600字

只输出正文，不加标题、不加Markdown格式。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.7)
            if len(result) < 150:
                expand_prompt = f"请将以下通俗解释扩展到至少400字：\n{result}"
                result = self.ai.chat(expand_prompt, temperature=0.7)
            return result
        except Exception:
            return f"（新人版通俗解释生成中）\n\n简单来说，这个问题是关于{question[:50]}...\n\n核心结论：{verdict[:100]}"

    def _render_expert(self, question: str, debate_rounds: List[Dict], atomic: Dict, judge_result: Dict) -> str:
        """生成专家版（含完整9人评分矩阵、审计综述、决策逻辑）"""
        scorecard = judge_result.get("role_scorecard", [])
        verdict = judge_result.get("final_verdict", "")
        rejected = judge_result.get("rejected_items", [])
        
        # 确保所有9个角色都在 scorecard 中
        all_roles = [
            "激进者", "保守者", "结构主义者", "百灵鸟", "取经者",
            "奇谋者", "延安智者", "大法官", "首席发言人",
        ]
        existing_roles = {item.get("role") for item in scorecard}
        for role in all_roles:
            if role not in existing_roles:
                scorecard.append({
                    "role": role,
                    "core_view": "（观点待补充）",
                    "strength": 5,
                    "novelty": 5,
                    "feasibility": 5,
                    "evidence_quality": 5,
                    "relevance": 5,
                    "alignment": 5,
                    "activation": 5,
                    "contribution_percent": 0,
                    "status": "deferred",
                    "brief_reason": "数据不足"
                })
        
        # 构建完整评分矩阵
        matrix_lines = ["| 角色 | 论证力度 | 创新性 | 可落地性 | 证据质量 | 相关性 | 原则一致性 | 认知激活 | 贡献度 | 状态 |"]
        matrix_lines.append("|------|---------|--------|---------|---------|--------|-----------|---------|--------|------|")
        for item in scorecard:
            role = item.get('role', '未知')
            matrix_lines.append(
                f"| {role} | {item.get('strength', 5)} | {item.get('novelty', 5)} | "
                f"{item.get('feasibility', 5)} | {item.get('evidence_quality', 5)} | "
                f"{item.get('relevance', 5)} | {item.get('alignment', 5)} | "
                f"{item.get('activation', 5)} | {item.get('contribution_percent', 0)}% | "
                f"{item.get('status', 'deferred')} |"
            )
        matrix_table = "\n".join(matrix_lines)
        
        # 构建各角色核心观点
        role_views = []
        for item in scorecard[:9]:
            role = item.get("role", "")
            core = item.get("core_view", "观点待补充")
            if core and core != "（观点待补充）":
                role_views.append(f"**{role}**：{core}")
        role_view_text = "\n\n".join(role_views) if role_views else "（各角色观点待补充）"
        
        # 构建驳回明细
        rejected_text = ""
        if rejected:
            rejected_text = "\n".join([f"- {item.get('item', '')}: {item.get('reason', '')}" for item in rejected])
        else:
            rejected_text = "无驳回项"
        
        prompt = f"""
你是「首席发言人」的助理，负责生成专家级详细决策报告。

【问题】
{question}

【终审裁决】
{verdict}

【7项KPI评分矩阵（完整9人）】
{matrix_table}

【各角色核心观点】
{role_view_text}

【驳回明细】
{rejected_text}

【要求】
请生成一份专家级详细报告，包含：
1. 决策摘要（100字内）
2. 评分矩阵分析（逐角色解读KPI表现）
3. 决策逻辑链条（推理过程）
4. 风险与边界条件
5. 实施建议

【风格要求】
- 客观、严谨、数据驱动
- 引用具体的KPI分数
- 报告开头用一句话给出“人话版结论”，专业术语首次出现时用括号解释
- 字数：800-1500字
- 使用Markdown格式

请直接输出报告正文。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.5)
            if len(result) < 400:
                expand_prompt = f"请将以下专家报告扩展到至少800字，补充评分矩阵分析：\n{result}"
                result = self.ai.chat(expand_prompt, temperature=0.5)
            return result
        except Exception:
            return f"（专家版详细报告生成中）\n\n{verdict}\n\n评分矩阵：\n{matrix_table}"


    def _render_elegant(self, judge_result: Dict) -> str:
        """生成儒雅笔谈"""
        verdict = judge_result.get("final_verdict", "")
        scorecard = judge_result.get("role_scorecard", [])
        adopted = [item.get("role", "") for item in scorecard if item.get("status") == "adopted"]
        adopted_text = "、".join(adopted[:3]) if adopted else "众智者"
        core_conclusion = verdict[:100] if len(verdict) > 100 else verdict
        
        prompt = f"""
你是一位深谙苏轼、辛弃疾文风的散文大家。请将以下决策内容改写为一段「儒雅风格」的文字。

【核心结论】
{core_conclusion}

【采纳角色】
{adopted_text}

【风格要求】
模仿苏轼的旷达通透与辛弃疾的豪迈沉郁——文字从容而有筋骨。

【具体要求】
1. 以"以我观之"或类似文人笔法开篇
2. 用一个自然意象（如山、水、月、竹、云）贯穿全文
3. 引用或化用一句古诗词
4. 结尾落在"行"字上——可行之道
5. 字数：120-200字
6. 不加标题、不加序号

只输出正文。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.75)
            if len(result) < 80:
                expand_prompt = f"请将以下儒雅笔谈扩展到至少120字：\n{result}"
                result = self.ai.chat(expand_prompt, temperature=0.75)
            return result
        except Exception:
            return f"以我观之，此事如月照寒潭，明澈而深邃。{core_conclusion}。行者自知，行之者自达。"

    def _polish_final_report(self, raw_report: str, max_words: int = 600) -> str:
        """
        终稿润色师：将 5 份原始报告压缩为 400-600 字高信息密度交付物
        删除冗余、自然语言化晶体引用、结论先行
        """
        if not raw_report or len(raw_report) < 200:
            return raw_report

        # 提取核心结论（取第一段或首句）
        sentences = raw_report.split('\n')
        core = []
        for s in sentences:
            if s.strip():
                core.append(s.strip())
                if len(''.join(core)) > 300:
                    break

        # 如果太长，截断并添加省略号
        polished = ' '.join(core)
        if len(polished) > max_words:
            # 尽量在句子边界截断
            cut = polished[:max_words]
            last_period = cut.rfind('。')
            if last_period > max_words * 0.8:
                polished = cut[:last_period+1] + "......（后略）"
            else:
                polished = cut + "......"

        # 自然语言化晶体引用（将 [Cxxx] 替换为 "晶体 Cxxx 指出"）
        polished = re.sub(r'\[C(\d+)\]', r'晶体 C\1 指出', polished)
        polished = re.sub(r'\[H(\d+)\]', r'孔洞 H\1', polished)

        return polished

                       
# ===== 看板数据聚合 =====
def compute_dashboard_stats(judge_audit: Dict) -> Dict[str, int]:
    stats = {"adopted": 0, "conditional": 0, "deferred": 0, "rejected": 0}
    scorecard = judge_audit.get("role_scorecard", []) or judge_audit.get("by_rule", [])
    for item in scorecard:
        status = item.get("status", item.get("state", ""))
        if status in stats:
            stats[status] += 1
    stats["total"] = sum(stats.values())
    return stats

# ===== 一键补丁初始化 =====
