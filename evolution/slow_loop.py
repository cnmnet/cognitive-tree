"""Slow loop: online replay and rollback decision."""

from __future__ import annotations

from typing import Any, Dict, List


class SlowLoop:
    def __init__(self, min_improvement: float = 0.03, metrics: List[str] | None = None) -> None:
        self.min_improvement = min_improvement
        self.metrics = metrics or ["jaccard", "crystal_reference_rate", "audit_feedback_length"]

    def decide(self, baseline: Dict[str, float], current: Dict[str, float]) -> Dict[str, Any]:
        deltas = {}
        for metric in self.metrics:
            deltas[metric] = current.get(metric, 0.0) - baseline.get(metric, 0.0)
        improvement = sum(deltas.values()) / max(1, len(deltas))
        rollback = improvement < self.min_improvement
        return {
            "rollback": rollback,
            "improvement": round(improvement, 4),
            "deltas": deltas,
        }
