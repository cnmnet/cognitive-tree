#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地八维评分（workbuddy 风格启发式），零依赖，供回复与基线跑分共用。"""

from __future__ import annotations

import re


SECTIONS = ["执行摘要", "角色分析", "分歧", "裁决", "实施", "风险", "止损", "来源索引"]
ROLES = [
    "激进者",
    "保守者",
    "结构主义者",
    "百灵鸟",
    "取经者",
    "奇谋者",
    "延安智者",
    "大法官",
    "首席发言人",
]
DEPTH_WORDS = [
    "因果",
    "归因",
    "模型",
    "机制",
    "结构",
    "框架",
    "逻辑",
    "证据",
    "假设",
    "验证",
    "分层",
    "双轨",
    "边际",
    "杠杆",
]
LOGIC_WORDS = [
    "因为",
    "所以",
    "因此",
    "由于",
    "如果",
    "那么",
    "但是",
    "然而",
    "反例",
    "假设",
    "条件",
    "否则",
    "从而",
]
INNOVATION_WORDS = [
    "认知",
    "第二曲线",
    "护城河",
    "双轨",
    "分层",
    "杠杆",
    "反直觉",
    "降维",
    "涌现",
    "自组织",
    "风险边界",
    "实证",
    "复用",
]
JARGON_WORDS = [
    "拓扑",
    "Gf",
    "Gc",
    "SOP",
    "GSP",
    "TMS",
    "SLA",
    "KPI",
    "API",
    "模型",
    "架构",
    "范式",
    "涌现",
    "认知层",
    "中台",
]
PRACTICAL_WORDS = [
    "第一步",
    "第二步",
    "第三步",
    "行动",
    "步骤",
    "止损",
    "预算",
    "时间节点",
    "里程碑",
    "风险矩阵",
    "路线图",
    "复购",
    "毛利率",
    "客户留存",
]
DIMENSION_LABELS = [
    ("argument_depth", "论证深度"),
    ("evidence_quality", "证据质量"),
    ("logic_rigor", "逻辑严谨"),
    ("perspective_diversity", "视角多样"),
    ("innovation_insight", "创新洞察"),
    ("structure_organization", "结构组织"),
    ("readability", "可读性"),
    ("practical_value", "实用价值"),
]


def count_hits(text: str, words: list) -> int:
    return sum(1 for w in words if w in text)


def ends_complete(text: str) -> bool:
    tail = text.rstrip()
    return bool(tail) and tail[-1] in "。！？!?*"


def parse_sandbox_consistency(text: str) -> int:
    """返回 1 表示一致，0 表示无法判断，-1 表示矛盾。"""
    if "沙盒验证" not in text:
        return 0
    m_pass_rate = re.search(r"通过率[：:]\s*([\d.]+)%", text)
    detail_pass = text.count("✅ 通过")
    detail_fail = text.count("❌ 失败")
    if detail_pass + detail_fail == 0:
        return 0
    detail_rate = detail_pass / (detail_pass + detail_fail) * 100
    if m_pass_rate:
        stated_rate = float(m_pass_rate.group(1))
        return 1 if abs(stated_rate - detail_rate) < 1.0 else -1
    return 0


def score_report(text: str) -> dict:
    section_found = sum(1 for s in SECTIONS if s in text)
    role_found = sum(1 for r in ROLES if r in text)
    depth_hits = count_hits(text, DEPTH_WORDS)
    logic_hits = count_hits(text, LOGIC_WORDS)
    innovation_hits = count_hits(text, INNOVATION_WORDS)
    jargon_hits = count_hits(text, JARGON_WORDS)
    practical_hits = count_hits(text, PRACTICAL_WORDS)
    table_count = text.count("|---")
    source_count = len(re.findall(r"\[(arxiv|news|hf|external)\]|https?://", text))
    date_num_hits = len(
        re.findall(
            r"(202[0-9]年|202[0-9]-\d{1,2}-\d{1,2}|\d+\.?\d*\s*(%|元|万|亿|天|小时|分钟))",
            text,
        )
    )

    argument_depth = min(
        100,
        40 + 8 * section_found + 5 * min(depth_hits, 8) + 5 * min(role_found, 9),
    )
    evidence_quality = min(
        100,
        20
        + 12 * min(source_count, 5)
        + 8 * min(date_num_hits, 6)
        + 12 * (1 if "主张验证明细" in text else 0)
        + 10 * (parse_sandbox_consistency(text) == 1)
        + 8 * (1 if "M3MAD" in text else 0),
    )
    if parse_sandbox_consistency(text) == -1:
        evidence_quality -= 15
    logic_rigor = min(
        100,
        35
        + 4 * min(logic_hits, 10)
        + 8 * (1 if "如果" in text and "那么" in text else 0)
        + 8 * (1 if any(w in text for w in ("反例", "反驳", "然而")) else 0)
        + 5 * min(role_found, 9),
    )
    perspective_diversity = min(
        100,
        30
        + 6 * min(role_found, 9)
        + 15 * (1 if "分歧" in text else 0)
        + 10 * (1 if "共识" in text else 0)
        + 10 * (1 if "角色绩效看板" in text else 0),
    )
    innovation_insight = min(
        100,
        35
        + 4 * min(innovation_hits, 12)
        + 10 * (1 if any(w in text for w in ("双轨", "分层", "第二曲线", "护城河")) else 0),
    )
    structure_organization = min(
        100,
        40
        + 8 * min(section_found, 8)
        + 10 * (1 if ends_complete(text) else 0)
        + 10
        * (
            1
            if "API Key 无效" not in text
            and "执行失败" not in text
            and "待补充" not in text
            else 0
        )
        + 5 * min(text.count("##"), 6),
    )
    avg_sentence = len(text) / max(1, len(re.findall(r"[。！？!?；;\n]", text)))
    readability = min(
        100,
        45
        + 5 * min(table_count, 4)
        + 10 * (1 if "新人版" in text or "通俗" in text else 0)
        + 15 * max(0, 1 - min(jargon_hits, 10) / 10)
        + 10 * max(0, 1 - min(max(0, avg_sentence - 60) / 40, 1)),
    )
    practical_value = min(
        100,
        30
        + 5 * min(practical_hits, 8)
        + 10 * (1 if "止损" in text else 0)
        + 10 * (1 if "预算" in text else 0)
        + 10 * (1 if "KPI" in text or "客户留存" in text else 0)
        + 10 * (1 if "风险矩阵" in text or "风险清单" in text else 0)
        + 10 * (1 if "路线图" in text or "阶段" in text else 0),
    )

    return {
        "argument_depth": round(argument_depth, 1),
        "evidence_quality": round(evidence_quality, 1),
        "logic_rigor": round(logic_rigor, 1),
        "perspective_diversity": round(perspective_diversity, 1),
        "innovation_insight": round(innovation_insight, 1),
        "structure_organization": round(structure_organization, 1),
        "readability": round(readability, 1),
        "practical_value": round(practical_value, 1),
    }


def score_summary(scores: dict) -> float:
    return round(sum(scores.values()) / len(scores), 1)


def score_payload(text: str) -> dict:
    scores = score_report(text)
    return {"scores": scores, "total": score_summary(scores)}


def score_line(text: str) -> str:
    """给回答追加一行紧凑的八维评分结果。"""
    payload = score_payload(text)
    parts = [
        f"{label} {payload['scores'][key]}"
        for key, label in DIMENSION_LABELS
    ]
    return (
        f"\n\n【回答质量评分】{' | '.join(parts)} | 综合总分 {payload['total']}"
    )
