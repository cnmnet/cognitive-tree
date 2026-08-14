#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple


SECTION_ALIASES: Dict[str, List[str]] = {
    "结论": ["结论", "执行摘要", "核心结论", "终审裁决", "最终结论", "最终决策", "总结"],
    "理由": ["理由", "依据", "关键理由", "裁决理由", "原因"],
    "下一步": ["下一步", "行动", "实施建议", "建议", "行动清单", "路线"],
    "止损": ["止损", "红线", "退出线", "风险清单", "预警"],
    "通俗解释": ["新人版", "通俗解释", "新人能理解"],
    "老板版": ["老板版", "决策摘要"],
    "员工版": ["员工版", "SOP", "操作手册"],
    "专家版": ["专家版", "详细报告"],
    "儒雅笔谈": ["儒雅笔谈", "epilogue"],
}
ERROR_PREFIXES = ("错误", "API Key", "AI调用失败", "请求超时", "网络连接失败")
PLACEHOLDER_MARKERS = ("待补充", "占位", "TODO", "待人工补充")
ORIGINAL_REPORT_TARGET = 25000
COMPRESSED_REPORT_TARGET = 5000
QUICK_VIEW_TARGET = 800
PERFORMANCE_BOARD_ROLES = [
    "激进者", "保守者", "结构主义者", "百灵鸟", "取经者",
    "奇谋者", "延安智者", "大法官", "首席发言人",
]


@dataclass
class CompressionContract:
    """压缩版硬契约：字数、结构、重试与降级规则。"""

    max_chars: int = 6000
    min_chars: int = 0
    required_sections: List[str] = field(default_factory=lambda: ["结论", "理由", "下一步"])
    optional_sections: List[str] = field(default_factory=lambda: ["止损"])
    retries: int = 1


def _contains_section(text: str, section: str) -> bool:
    aliases = SECTION_ALIASES.get(section, [section])
    return any(alias in text for alias in aliases)


def _validate_compressed(text: str, contract: CompressionContract, required: List[str]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    text = (text or "").strip()
    if not text:
        return False, ["输出为空"]
    if len(text) > contract.max_chars:
        reasons.append(f"超过字数上限 {contract.max_chars}")
    if len(text) < contract.min_chars:
        reasons.append(f"字数不足 {contract.min_chars}")
    for section in required:
        if not _contains_section(text, section):
            reasons.append(f"缺少必需结构：{section}")
    for prefix in ERROR_PREFIXES:
        if text.startswith(prefix):
            reasons.append(f"输出包含错误前缀：{prefix}")
            break
    for marker in PLACEHOLDER_MARKERS:
        if marker in text:
            reasons.append(f"输出包含占位/未完成标记：{marker}")
    if len(text) >= contract.max_chars * 0.8:
        tail = text.rstrip()
        if tail and tail[-1] not in "。！？!?；;）】\"'*":
            reasons.append("疑似截断：结尾不完整")
    return (not reasons, reasons)


def _compression_candidate_score(text: str, contract: CompressionContract, required: List[str]) -> int:
    """给 AI 压缩候选打分：结构完整且接近字数上限的优先，占位符重罚。"""
    text = (text or "").strip()
    if not text:
        return -1
    score = 0
    for marker in PLACEHOLDER_MARKERS:
        if marker in text:
            score -= 2000
    for section in required:
        if _contains_section(text, section):
            score += 20
    score += min(len(text), contract.max_chars)
    if len(text) > contract.max_chars:
        score -= (len(text) - contract.max_chars) * 2
    return score


def validate_compressed(text: str, contract: CompressionContract = None) -> Tuple[bool, List[str]]:
    """公开校验入口：检查压缩输出是否满足契约。"""
    contract = contract or CompressionContract()
    required = list(contract.required_sections)
    return _validate_compressed(text, contract, required)


def _extract_heading_block(text: str, keywords: List[str], max_lines: int = 4) -> str:
    lines = text.splitlines()
    idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (stripped.startswith("#") or stripped.startswith("**")) and any(k in stripped for k in keywords):
            idx = i
            break
    if idx is None:
        for i, line in enumerate(lines):
            if any(k in line for k in keywords):
                idx = i
                break
    if idx is None:
        return ""
    block = []
    for line in lines[idx + 1:]:
        stripped = line.strip()
        if not stripped:
            if block:
                break
            continue
        if stripped.startswith("#") or stripped == "---":
            break
        if len(block) >= max_lines:
            break
        block.append(stripped[:100])
    return " ".join(block).strip()


def _truncate_at_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    idx = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"), cut.rfind("；"), cut.rfind("!?"))
    if idx >= max_chars * 0.5:
        return cut[:idx + 1]
    return cut.rstrip()


def _rule_based_compress(full_report: str, contract: CompressionContract, required: List[str]) -> str:
    parts = []
    for section in required:
        text = _extract_heading_block(full_report, SECTION_ALIASES.get(section, [section]))
        if not text:
            text = "（原文未明确给出，建议人工补充）"
        parts.append(f"## {section}\n{text}")
    return _truncate_at_boundary("\n\n".join(parts), contract.max_chars)


def _compression_prompt(full_report: str, contract: CompressionContract, required: List[str],
                        system_hint: str, feedback: str) -> str:
    required_text = "、".join(required)
    feedback_text = f"\n【上次校验未通过】{feedback}\n" if feedback else ""
    return f"""你是顶级报告编辑。请把完整报告压缩成 4000-{contract.max_chars} 字的精炼交付物；字数少于 3500 会被退回重写，请尽量接近 {contract.max_chars} 字。

【结构要求】
必须包含结构：{required_text}。
结论：300-500 字，给出最终决策、核心立场、评估基准和一句话总预算/周期；
理由：1200-1800 字，保留 3-5 条关键论证，说明决策依据，尽量保留原报告中的证据编号（如 [E001]）与关键数据；
下一步：1200-1800 字，给出 3-5 项可执行行动，保留原报告中的阶段、预算、里程碑、责任分工，可用表格；
止损：500-800 字，保留原报告中的止损线、触发阈值、触发动作，可用表格。
结尾可附「附：关键决策要点速查」，保留对比表格、来源索引、术语对照。
禁止空话；禁止编造；禁止“待补充/占位”类标记。
直接输出 Markdown，不要额外解释。{feedback_text}

【完整报告】
{full_report}
"""


def compress_report_with_contract(full_report: str, ai_client=None,
                                  contract: CompressionContract = None,
                                  system_hint: str = "") -> str:
    """压缩完整报告并强制执行硬契约：校验 → 重试 → 规则降级。"""
    contract = contract or CompressionContract()
    if not full_report or not full_report.strip():
        return ""
    if len(full_report) <= contract.max_chars:
        return full_report

    required = list(contract.required_sections)
    for section in contract.optional_sections:
        if _contains_section(full_report, section):
            required.append(section)

    feedback = ""
    best = ""
    best_score = -1
    if ai_client is not None:
        max_tokens = max(600, min(8000, int(contract.max_chars * 2.5)))
        for _attempt in range(contract.retries + 1):
            prompt = _compression_prompt(full_report, contract, required, system_hint, feedback)
            try:
                result = ai_client.chat(
                    prompt,
                    system=system_hint or "你是报告压缩专家，输出精炼、结构清晰、不超字数的报告。",
                    temperature=0.4,
                    max_tokens=max_tokens,
                )
            except Exception:
                result = ""
            if isinstance(result, str) and result.strip():
                result = result.strip()
                ok, reasons = _validate_compressed(result, contract, required)
                if ok:
                    return result
                if all(_contains_section(result, section) for section in required):
                    score = _compression_candidate_score(result, contract, required)
                    if score > best_score:
                        best, best_score = result, score
                feedback = "；".join(reasons)
        if best:
            return best
    return _rule_based_compress(full_report, contract, required)

def _dedupe_headings(text: str) -> str:
    """去掉同一角色发言中重复出现的步骤标题（保留首个）。"""
    seen = set()
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("**第") and stripped.endswith("**"):
            if stripped in seen:
                continue
            seen.add(stripped)
        out.append(line)
    return "\n".join(out)


def _join_broken_lines(text: str) -> str:
    """合并被换行切断的中文词（如“端到/端到端”）。"""
    lines = text.splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        if out and stripped and not stripped.startswith(("#", "|", "-", "*", ">", "```", "```")):
            prev = out[-1]
            if prev and not prev.startswith(("#", "|", "-", "*", ">", "```")):
                last_char = prev[-1]
                if len(prev) < 80 and len(stripped) < 80 and last_char not in "。！？!?；;，,：:—…":
                    out[-1] = prev + line
                    continue
        out.append(line)
    return "\n".join(out)


def _extract_step_blocks(text: str) -> list:
    """提取“第一步/Step 1/第一阶段”等步骤及其后续内容，用于 30/60/90 清单。"""
    if not text:
        return []
    pattern = re.compile(r'(第[一二三]步|Step\s*[123]|第一阶段|第二阶段|第三阶段)[：:]*[^\n]*')
    matches = list(pattern.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = re.sub(r'\s+', ' ', text[m.start():end]).strip()
        if len(block) > 12:
            blocks.append(block[:220])
    return blocks

def _render_decision_annex(annex: Dict) -> List[str]:
    """把结构化决策附录渲染成 Markdown 段落。"""
    lines: List[str] = []
    final_decision = annex.get("final_decision") or ""
    if final_decision:
        lines.append("### 最终决策")
        lines.append("")
        lines.append(final_decision)
        lines.append("")

    resource = annex.get("resource_allocation") or {}
    if resource:
        lines.append("### 资源分配")
        lines.append("")
        lines.append(f"- **比例**：{resource.get('ratio') or '见终审裁决'}")
        lines.append(f"- **说明**：{resource.get('detail') or '见终审裁决'}")
        lines.append("")

    budget = annex.get("budget") or []
    if budget:
        lines.append("### 预算分解")
        lines.append("")
        lines.append("| 科目 | 金额 | 用途 |")
        lines.append("|------|------|------|")
        for item in budget:
            if isinstance(item, dict):
                lines.append(
                    f"| {item.get('item', '')} | {item.get('amount', '')} | {item.get('note', '')} |"
                )
        lines.append("")

    timeline = annex.get("timeline") or []
    if timeline:
        has_budget = any(isinstance(item, dict) and item.get("budget") for item in timeline)
        lines.append("### 执行时间线")
        lines.append("")
        if has_budget:
            lines.append("| 阶段 | 预算 | 关键动作 | 里程碑 |")
            lines.append("|------|------|----------|--------|")
            for item in timeline:
                if isinstance(item, dict):
                    lines.append(
                        f"| {item.get('phase', '')} | {item.get('budget', '')} | "
                        f"{item.get('actions', '')} | {item.get('milestone', '')} |"
                    )
        else:
            lines.append("| 阶段 | 关键动作 | 里程碑 |")
            lines.append("|------|----------|--------|")
            for item in timeline:
                if isinstance(item, dict):
                    lines.append(
                        f"| {item.get('phase', '')} | {item.get('actions', '')} | {item.get('milestone', '')} |"
                    )
        lines.append("")

    stop_loss = annex.get("stop_loss") or []
    if stop_loss:
        lines.append("### 止损线")
        lines.append("")
        lines.append("| 监测指标 | 触发阈值 | 触发动作 |")
        lines.append("|----------|----------|----------|")
        for item in stop_loss:
            if isinstance(item, dict):
                lines.append(
                    f"| {item.get('metric', '')} | {item.get('threshold', '')} | {item.get('action', '')} |"
                )
        lines.append("")

    risk_control = annex.get("risk_control") or []
    if risk_control:
        lines.append("### 风险与合规")
        lines.append("")
        lines.append("| 风险项 | 等级 | 缓释措施 |")
        lines.append("|--------|------|----------|")
        for item in risk_control:
            if isinstance(item, dict):
                lines.append(
                    f"| {item.get('risk', '')} | {item.get('level', '')} | {item.get('mitigation', '')} |"
                )
        lines.append("")

    acceptance = annex.get("acceptance_criteria") or []
    if acceptance:
        lines.append("### 验收标准")
        lines.append("")
        for item in acceptance:
            if isinstance(item, str):
                lines.append(f"- {item}")
            elif isinstance(item, dict):
                lines.append(f"- {item.get('criterion', item.get('item', ''))}")
        lines.append("")

    owners = annex.get("owners") or []
    if owners:
        lines.append("### 责任分工")
        lines.append("")
        lines.append("| 岗位/角色 | 职责 |")
        lines.append("|-----------|------|")
        for item in owners:
            if isinstance(item, dict):
                lines.append(f"| {item.get('role', '')} | {item.get('responsibility', '')} |")
        lines.append("")
    return lines


def ensure_performance_board(scorecard: List[Dict]) -> List[Dict]:
    """确保绩效看板覆盖全部9个角色，缺失项以默认展示行补齐。"""
    if not scorecard:
        return scorecard
    existing = {item.get("role") for item in scorecard}
    for role in PERFORMANCE_BOARD_ROLES:
        if role in existing:
            continue
        scorecard.append({
            "role": role,
            "core_view": "（本轮未参与评审）",
            "strength": 5,
            "novelty": 5,
            "feasibility": 5,
            "evidence_quality": 5,
            "relevance": 5,
            "alignment": 5,
            "activation": 5,
            "kpi_score": 5,
            "contribution_percent": 0,
            "status": "deferred",
            "brief_reason": "补充展示",
        })
    return scorecard


def build_debate_report_markdown(question: str, result: Dict, board_version: str,
                                 employee_version: str, novice_version: str,
                                 expert_version: str, judge_audit: Dict) -> str:
    """构建完整辩论报告 Markdown（GUI 与命令行共用）。"""
    lines = []
    lines.append("# 📋 辩论报告")
    lines.append("")
    lines.append(f"**问题**：{question}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 第一部分 · 辩论正文")
    lines.append("")
    lines.append("> 本部分保留多角色完整交锋、攻防与裁决过程；可执行结论以第二部分「决策附录」为准。")
    lines.append("")

    rounds_data = result.get("rounds", [])
    lines.append("## 各角色核心观点")
    lines.append("")
    role_views = {}
    for rd in rounds_data:
        if rd.get("round", 0) == 0:
            continue
        for ans in rd.get("answers", []):
            role_name = ans.get('role', '未知角色')
            if role_name in role_views:
                continue
            role_views[role_name] = ans.get('answer', '（无回答）')

    role_order = [
        "激进者", "保守者", "结构主义者", "百灵鸟", "取经者",
        "奇谋者", "延安智者", "大法官", "首席发言人",
    ]
    for role in role_order:
        if role in role_views:
            lines.append(f"### {role}")
            lines.append("")
            lines.append(_join_broken_lines(_dedupe_headings(role_views[role])))
            lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## 大法官裁决")
    lines.append("")
    scorecard = judge_audit.get("role_scorecard", []) or judge_audit.get("by_rule", [])
    if scorecard:
        scorecard = ensure_performance_board(list(scorecard))
        lines.append("### 角色绩效看板")
        lines.append("")
        lines.append("| 角色 | 贡献度 | KPI | 状态 | 核心理由 |")
        lines.append("|------|--------|-----|------|----------|")
        status_map = {"adopted": "✅采纳", "conditional": "⚠️附条件", "deferred": "⏸暂缓", "rejected": "❌驳回"}
        for item in scorecard:
            status = status_map.get(item.get("status", "deferred"), "⏸暂缓")
            kpi_values = [
                item.get(k, 5) for k in
                ("strength", "novelty", "feasibility", "evidence_quality", "relevance", "alignment", "activation")
            ]
            kpi_score = sum(kpi_values) / len(kpi_values)
            lines.append(
                f"| {item.get('role', '未知')} | "
                f"{item.get('contribution_percent', 0):.0f}% | "
                f"{kpi_score:.1f}/10 | "
                f"{status} | "
                f"{item.get('brief_reason', '')} |"
            )
        lines.append("")
        lines.append("### 裁决理由明细")
        lines.append("")
        status_cn = {"adopted": "采纳", "conditional": "附条件采纳", "deferred": "暂缓", "rejected": "驳回"}
        for item in scorecard:
            role = item.get("role", "未知")
            st = status_cn.get(item.get("status", "deferred"), "待定")
            reason = item.get("brief_reason", "")
            basis = item.get("system_basis", "")
            lines.append(f"- **{role}**：{st}。{reason}。依据：{basis or '（未提供具体依据）'}")
        rejected_items = judge_audit.get("rejected_items", [])
        if rejected_items:
            lines.append("")
            lines.append("驳回明细：")
            for ri in rejected_items:
                lines.append(f"  - {ri.get('item', '')}：{ri.get('reason', '')}")
        lines.append("")

    final_verdict = judge_audit.get("final_verdict") or judge_audit.get("summary", "")
    if final_verdict:
        lines.append("### 终审裁决")
        lines.append("")
        lines.append(final_verdict)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 首席发言人叙事")
    lines.append("")
    lines.append("> 说明：以下为辩论正文中的多受众阐释，属角色个人主张，非终审裁决；最终可执行结论以第二部分「决策附录」为准。")
    lines.append("")
    versions = [
        ("老板版 - 决策摘要", board_version),
        ("员工版 - SOP操作手册", employee_version),
        ("新人版 - 通俗解释", novice_version),
        ("专家版 - 详细报告", expert_version),
    ]
    for title, content in versions:
        if content and content.strip():
            lines.append(f"### {title}")
            lines.append("")
            lines.append(content)
            lines.append("")

    elegant_epilogue = result.get("elegant_epilogue", "")
    if elegant_epilogue:
        lines.append("### 儒雅笔谈")
        lines.append("")
        lines.append(elegant_epilogue)
        lines.append("")

    decision_annex = result.get("decision_annex") or {}
    if decision_annex:
        lines.append("---")
        lines.append("")
        lines.append("## 第二部分 · 决策附录（可执行版）")
        lines.append("")
        lines.append("> 本部分为大法官终审后的结构化决策，可直接用于执行与验收；所有数字应通过算术自洽门核验。")
        lines.append("")
        lines.extend(_render_decision_annex(decision_annex))
        lines.append("")

    day12_data = result.get("_day12", {})
    if day12_data:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 第三部分 · 验证与来源材料")
        lines.append("")
        lines.append("## 🔬 沙盒验证结果")
        lines.append("")
        claims_count = day12_data.get("claims_extracted", 0)
        verified_count = day12_data.get("verified_count", 0)
        pending_count = day12_data.get("pending_review_count", 0)
        failed_count = day12_data.get("failed_count", 0)
        asserted_count = day12_data.get("asserted_count", 0)
        numeric_count = day12_data.get("numeric_claim_count", max(0, claims_count - pending_count))
        source_count = day12_data.get("source_claim_count", 0)
        logic_count = day12_data.get("logic_claim_count", 0)
        m3mad_score = day12_data.get("m3mad_bench", {}).get("overall_score", 0)
        lines.append(f"- **主张总数**：{claims_count} 条")
        lines.append(f"- **数字主张**：{numeric_count} 条")
        lines.append(f"- **来源主张**：{source_count} 条")
        lines.append(f"- **逻辑主张**：{logic_count} 条")
        lines.append(f"- **沙盒验证通过**：{verified_count} 条")
        lines.append(f"- **待人工核验**：{pending_count} 条")
        lines.append(f"- **未通过**：{failed_count} 条")
        if asserted_count > 0:
            lines.append(f"- **已断言主张通过率**：{verified_count / asserted_count * 100:.1f}%")
        else:
            lines.append("- **已断言主张通过率**：N/A")
        lines.append(f"- **M3MAD综合评分**：{m3mad_score:.2f}/1.00")
        claims = day12_data.get("claims", [])
        if claims:
            lines.append("")
            lines.append("### 主张验证明细")
            lines.append("")
            lines.append("| 主张 | 类型 | 状态 |")
            lines.append("|------|------|------|")
            for claim in claims[:15]:
                claim_text = claim.get("original_text", "")[:60]
                claim_type = claim.get("claim_type", "")
                verification_status = claim.get("result", {}).get("verification_status", "")
                if verification_status == "verified":
                    status = "✅ 通过"
                elif verification_status == "failed":
                    status = "❌ 失败"
                elif claim_type in ("source", "logic") or verification_status in ("pending_review", ""):
                    status = "⏳ 待人工核验"
                else:
                    status = "❌ 失败"
                lines.append(f"| {claim_text} | {claim_type} | {status} |")
            if len(claims) > 15:
                lines.append(f"| ... 还有 {len(claims) - 15} 条 | | |")
            lines.append("")
        lines.append("---")
        lines.append("")

    source_items = list(day12_data.get("sources", [])) if day12_data else []
    if not source_items:
        for rd in rounds_data:
            for ans in rd.get("answers", []):
                answer_text = ans.get("answer", "")
                for m in re.finditer(r'\[(arxiv|news|hf|external)\][^\n]{0,100}|https?://\S+', answer_text):
                    item = m.group(0).strip()
                    if item not in source_items:
                        source_items.append(item)
        for v in (board_version, employee_version, novice_version, expert_version):
            if not v:
                continue
            for m in re.finditer(r'\[(arxiv|news|hf|external)\][^\n]{0,100}|https?://\S+', v):
                item = m.group(0).strip()
                if item not in source_items:
                    source_items.append(item)
    if source_items:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 📚 来源索引")
        lines.append("")
        for src in source_items[:50]:
            lines.append(f"- {src}")
        lines.append("")

    glossary = {
        "SOP": "标准作业流程，照做的操作手册",
        "KPI": "关键绩效指标，衡量做得好不好的数字",
        "GSP": "药品经营质量管理规范，医药运输资质",
        "TMS": "运输管理系统，管车管单管路线的软件",
        "SLA": "服务水平协议，承诺的响应时限",
        "API": "应用程序接口，系统间传数据的通道",
        "中台": "公司内部共享能力中心",
        "SVR-MAD": "贝叶斯可信角色验证方法",
    }
    report_so_far = "\n".join(lines)
    glossary_hits = [f"{k}：{v}" for k, v in glossary.items() if k in report_so_far]
    if glossary_hits:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 🗣 术语白话对照")
        lines.append("")
        for item in glossary_hits:
            lines.append(f"- {item}")
        lines.append("")

    action_items = _extract_step_blocks(expert_version or "")
    if not action_items:
        for rd in rounds_data:
            for ans in rd.get("answers", []):
                action_items = _extract_step_blocks(ans.get("answer", ""))
                if len(action_items) >= 3:
                    break
            if len(action_items) >= 3:
                break
    seen_actions = set()
    unique_actions = []
    for action in action_items:
        key = action.split("：")[0] if "：" in action else action[:8]
        if key not in seen_actions:
            seen_actions.add(key)
            unique_actions.append(action)
    action_items = unique_actions[:3]
    if action_items:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 🗓 30/60/90 天行动清单")
        lines.append("")
        labels = ["30天", "60天", "90天"]
        for i, item in enumerate(action_items[:3]):
            label = labels[i] if i < 3 else f"第{i + 1}步"
            lines.append(f"- **{label}**：{item}")
        lines.append("")

    lines.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    return "\n".join(lines)

def polish_report_markdown(full_report: str, ai_client=None, max_len: int = COMPRESSED_REPORT_TARGET) -> str:
    """润色压缩报告：通过压缩版硬契约（字数/结构校验、重试、规则降级）。"""
    if not full_report or len(full_report) <= max_len:
        return full_report
    contract = CompressionContract(
        max_chars=max_len,
        min_chars=min(max_len, max(800, int(max_len * 0.7))),
        retries=2,
    )
    return compress_report_with_contract(
        full_report,
        ai_client=ai_client,
        contract=contract,
        system_hint=f"你是报告压缩专家，输出精炼、结构清晰、不超过 {max_len} 字的报告。",
    )


def limit_original_report(full_report: str, ai_client=None, max_chars: int = ORIGINAL_REPORT_TARGET) -> str:
    """完整版收束：目标 25000 字，超出时用硬契约收束，保留全部章节结构。"""
    if not full_report or len(full_report) <= max_chars:
        return full_report
    contract = CompressionContract(
        max_chars=max_chars,
        required_sections=["结论", "理由", "下一步", "通俗解释"],
        optional_sections=["止损", "老板版", "员工版", "专家版", "儒雅笔谈"],
    )
    return compress_report_with_contract(
        full_report,
        ai_client=ai_client,
        contract=contract,
        system_hint=f"你是报告编辑，把完整报告收束到 {max_chars} 字以内，保留全部章节结构。",
    )


def build_quick_view_report(full_report: str, ai_client=None, max_chars: int = QUICK_VIEW_TARGET) -> str:
    """速览版：800 字以内，给 30 秒决策的人看。"""
    if not full_report:
        return ""
    contract = CompressionContract(
        max_chars=max_chars,
        required_sections=["结论", "理由", "下一步"],
        optional_sections=["止损"],
    )
    return compress_report_with_contract(
        full_report,
        ai_client=ai_client,
        contract=contract,
        system_hint=f"你是报告编辑，输出不超过 {max_chars} 字的速览版，只保留决策要点。",
    )

