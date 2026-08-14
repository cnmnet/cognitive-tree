"""DAG 演示处理器：供 CLI 流程与测试使用，不做真实业务接线。"""

from __future__ import annotations

from typing import Any, Dict


class BaselineProcessor:
    name = "baseline"

    def process(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        rounds = params.get("rounds", 2)
        return {
            "questions": 10,
            "rounds": rounds,
            "status": "ok",
        }


class RetrievalProcessor:
    name = "retrieval"

    def process(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        scope = params.get("scope", "global")
        return {
            "scope": scope,
            "crystals": 0 if scope == "class" else 5,
            "status": "ok",
        }


class DebateProcessor:
    name = "debate"

    def process(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        mode = params.get("mode", "debate_full")
        if mode == "education":
            roles = ["考纲专家", "一线教师", "学生视角", "家长沟通者", "质量审计"]
        else:
            roles = ["激进者", "保守者", "结构主义者", "执行者", "审计者"]
        return {
            "mode": mode,
            "roles": roles,
            "rounds": 1 if mode == "education" else 3,
            "status": "ok",
        }


class ReportProcessor:
    name = "report"

    def process(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        style = params.get("style", "standard")
        if style == "education":
            versions = ["教师速览", "教学操作", "家长版", "学生版", "专家版"]
        else:
            versions = ["老板版", "员工版", "新人版", "专家版", "儒雅版"]
        return {
            "style": style,
            "versions": versions,
            "status": "ok",
        }


class PlannerProcessor:
    name = "planner"

    def process(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        return {
            "plan": ["基线", "辩论", "报告", "审计"],
            "status": "ok",
        }
