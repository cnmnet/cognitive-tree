"""Config governance: proposal, debate-on-config and auditor."""

from __future__ import annotations

from typing import Any, Dict


def proposal(change: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "proposed",
        "change": change,
    }


def debate_on_config(proposed: Dict[str, Any]) -> Dict[str, Any]:
    change = proposed.get("change", {})
    risks = len(change.get("risks", []))
    proposed["debate"] = {"rounds": 1, "risks_identified": risks}
    return proposed


def auditor(debated: Dict[str, Any], min_accept: float = 0.6) -> Dict[str, Any]:
    score = 0.9 if not debated.get("change", {}).get("risks") else 0.5
    accepted = score >= min_accept
    return {
        "accepted": accepted,
        "score": score,
        "patch": debated.get("change"),
    }
