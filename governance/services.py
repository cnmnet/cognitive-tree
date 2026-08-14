"""配置治理服务：角色、Prompt 与规则相关能力。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from governance.config import Config


_DEFAULT_AUDIT_RULES: Dict[str, Any] = {
    "role_feedback_min_chars": 200,
    "role_feedback_expand_chars": 150,
    "role_feedback_section_min_chars": 30,
    "audit_max_retries": 2,
    "audit_role_max_chars": 1000,
    "round_summary_min_chars": 50,
    "round_summary_max_chars": 300,
}
AUDIT_RULES_PATH = Path(__file__).resolve().parent / "config" / "audit_rules.json"
ROLE_IDEOLOGIES_PATH = Path(__file__).resolve().parent / "config" / "role_ideologies.json"


def load_audit_rules() -> Dict[str, Any]:
    """加载审计规则：默认 JSON 优先，运行数据目录可覆盖。"""
    rules = dict(_DEFAULT_AUDIT_RULES)
    for path in (AUDIT_RULES_PATH, Config.DATA_ROOT / "核心配置" / "audit_rules.json"):
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    rules.update(data)
        except Exception:
            pass
    return rules


def validate_audit_rules(rules: Dict[str, Any]) -> List[str]:
    """校验审计规则：数值键必须为正数。"""
    errors: List[str] = []
    for key in (
        "role_feedback_min_chars",
        "role_feedback_expand_chars",
        "role_feedback_section_min_chars",
        "audit_max_retries",
        "audit_role_max_chars",
        "round_summary_min_chars",
        "round_summary_max_chars",
    ):
        value = rules.get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            errors.append(f"{key} 必须为正数")
    if not errors and rules.get("round_summary_max_chars", 0) < rules.get("round_summary_min_chars", 0):
        errors.append("round_summary_max_chars 不能小于 round_summary_min_chars")
    return errors


def load_role_ideologies() -> Dict[str, str]:
    """加载角色思想钢印：默认 JSON 优先，运行数据目录可覆盖。"""
    data: Dict[str, str] = {}
    for path in (ROLE_IDEOLOGIES_PATH, Config.DATA_ROOT / "核心配置" / "role_ideologies.json"):
        try:
            if path.exists():
                item = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(item, dict):
                    data.update(
                        {key: value for key, value in item.items() if isinstance(value, str)}
                    )
        except Exception:
            pass
    return data


def current_profile(profile_name: str) -> Dict[str, Any]:
    """按名称返回模式配置，未知名称回退到平衡模式。"""
    profiles = {
        "high_accuracy": Config.PROFILE_HIGH_ACCURACY,
        "balanced": Config.PROFILE_BALANCED,
        "economy": Config.PROFILE_ECONOMY,
    }
    return profiles.get(profile_name, Config.PROFILE_BALANCED)


def load_debate_roles(config: Any, file_io: Any) -> List[Dict[str, str]]:
    """读取辩论角色配置（GUI 口径），缺失时写默认配置并补齐角色。"""
    default = {
        "radical": {"name": "激进者", "instruction": "攻击默认前提，假设现有框架是错的，给出颠覆性方案。"},
        "conservative": {"name": "保守者", "instruction": "风险优先，假设资源有限，给出最可落地的稳健方案。"},
        "structural": {"name": "结构主义者", "instruction": "从已有晶体中寻找同构案例，用类比生成方案。"},
        "executor": {"name": "执行者", "instruction": "把方案拆成步骤、资源、时间和可检查的行动清单。"},
        "auditor": {"name": "审计者", "instruction": "检查证据、漏洞、冲突、过度推断和需要暂存的问题。"},
    }
    path = config.get_path("roles")
    if not path.exists():
        file_io.write("roles", json.dumps(default, ensure_ascii=False, indent=2))
        data = default
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    roles_list = []
    for key, val in data.items():
        roles_list.append(
            {
                "id": key,
                "key": key,
                "name": val.get("name", key),
                "instruction": val.get("instruction", ""),
            }
        )
    fallback_roles = [
        {
            "id": "radical",
            "key": "radical",
            "name": "激进者",
            "instruction": "攻击默认前提，假设现有框架是错的，给出颠覆性方案。",
        },
        {
            "id": "conservative",
            "key": "conservative",
            "name": "保守者",
            "instruction": "风险优先，假设资源有限，给出最可落地的稳健方案。",
        },
        {
            "id": "structural",
            "key": "structural",
            "name": "结构主义者",
            "instruction": "从已有晶体中寻找同构案例，用类比生成方案。",
        },
        {
            "id": "executor",
            "key": "executor",
            "name": "执行者",
            "instruction": "把方案拆成步骤、资源、时间和可检查的行动清单。",
        },
        {
            "id": "auditor",
            "key": "auditor",
            "name": "审计者",
            "instruction": "检查证据、漏洞、冲突、过度推断和需要暂存的问题。",
        },
    ]
    existing = {role.get("id") or role.get("key") for role in roles_list}
    for role in fallback_roles:
        if len(roles_list) >= 5:
            break
        if role["id"] not in existing:
            roles_list.append(role)
            existing.add(role["id"])
    return roles_list


def load_roles(files: Any) -> List[Dict[str, str]]:
    """读取辩论角色配置，缺失时回填默认角色。"""
    try:
        raw = json.loads(files.read("roles") or "{}")
    except json.JSONDecodeError:
        raw = {}

    roles = []
    for key, item in raw.items():
        if isinstance(item, dict):
            roles.append(
                {
                    "key": key,
                    "name": item.get("name", key),
                    "instruction": item.get("instruction", ""),
                }
            )

    fallback_keys = [
        "radical",
        "conservative",
        "structural",
        "judge",
        "spokesperson",
        "lark",
        "pilgrim",
        "strategist",
        "statesman",
    ]
    fallback_roles = {
        "radical": {
            "name": "激进者",
            "instruction": "攻击默认前提，假设现有框架是错的，给出颠覆性方案。",
        },
        "conservative": {
            "name": "保守者",
            "instruction": "风险优先，假设资源有限，给出最可落地的稳健方案。",
        },
        "structural": {
            "name": "结构主义者",
            "instruction": "从已有晶体中寻找同构案例，用类比生成方案。",
        },
        "judge": {
            "name": "大法官",
            "instruction": "以晶体卡片、核心操作原则和资源约束为准绳，做出终审裁决。必须明确引用依据（晶体ID、原则条款或约束条件），不得凭直觉判案。",
        },
        "spokesperson": {
            "name": "首席发言人",
            "instruction": "将内部辩论结论转化为清晰、简洁、无歧义的对外陈述。遵循降维（通俗化）、定调（不超过3条核心信息）、检验（老板读前100字能决策）三原则。",
        },
        "lark": {
            "name": "百灵鸟",
            "instruction": "见多识广的通用智能体，从外部世界（学术、产业、政策、跨学科）补充知识，打破信息茧房。在第二轮登场。",
        },
        "pilgrim": {
            "name": "取经者",
            "instruction": "以长期愿景和核心价值观为锚，防止短期利益或局部优化偏离最终使命。评估方案的可持续性和道德一致性。",
        },
        "strategist": {
            "name": "奇谋者",
            "instruction": "善于洞察人心、把握时机，敢押注非常规路径，捕捉机会窗口。评估方案能否借力打力、以奇制胜。",
        },
        "statesman": {
            "name": "延安智者",
            "instruction": "坚持调查研究，不唯上、不唯书、只唯实。从全局矛盾和主要矛盾切入，提出实事求是、可落地的综合方略。",
        },
    }

    existing_keys = {item["key"] for item in roles}
    for key in fallback_keys:
        if key not in existing_keys:
            roles.append(
                {
                    "key": key,
                    "name": fallback_roles[key]["name"],
                    "instruction": fallback_roles[key]["instruction"],
                }
            )
    return roles
