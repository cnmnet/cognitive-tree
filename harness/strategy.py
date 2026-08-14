"""Harness-side strategy adapters: RUMADController / CrystalEngine as EvolutionStrategy."""

from __future__ import annotations

from typing import Any, Dict

class RUMADStrategy:
    """把 RUMADController 包装为可注入的进化策略。"""

    name = "rumad"

    def __init__(self, controller: Any):
        self.controller = controller

    def run(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        if "state_key" in context and "available_actions" in context:
            action = self.controller.select_action(
                context["state_key"],
                context["available_actions"],
                context.get("round_num", 1),
            )
            return {"action": action}
        if "previous_answers" in context and "current_answers" in context:
            self.controller.update_with_result(
                context["previous_answers"],
                context["current_answers"],
                context.get("previous_audit") or {},
                context.get("current_audit") or {},
            )
            return {"last_reward": self.controller.last_reward}
        return self.controller.get_stats()


class HebbianStrategy:
    """把 CrystalEngine 的 Hebbian 奖励机制包装为可注入的进化策略。"""

    name = "hebbian"

    def __init__(self, engine: Any):
        self.engine = engine

    def run(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        rate = self.engine.record_hebbian_reward(
            context.get("kind", "activity"),
            crystal_ids=context.get("crystal_ids"),
            role_keys=context.get("role_keys"),
            reward=context.get("reward"),
            question=context.get("question"),
            task_type=context.get("task_type"),
            context=context.get("context"),
        )
        return {"rate": rate}
