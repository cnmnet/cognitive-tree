"""Evolution-side strategy adapters: GödelAgent / MetaLayer as EvolutionStrategy."""

from __future__ import annotations

from typing import Any, Dict

class GodelStrategy:
    """把 GödelAgent 包装为可注入的进化策略。"""

    name = "godel"

    def __init__(self, agent: Any):
        self.agent = agent

    def run(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        action = context.get("action", "cycle")
        if action == "recursive":
            return self.agent.run_recursive_evolution_cycle()
        role_name = context.get("role_name") or params.get("role_name", "radical")
        return self.agent.run_evolution_cycle(role_name=role_name)


class MetaStrategy:
    """把 MetaLayer 包装为可注入的进化策略。"""

    name = "meta"

    def __init__(self, layer: Any):
        self.layer = layer

    def run(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        if context.get("action") == "dual_loop":
            return self.layer.run_dual_loop(
                max_merges=params.get("max_merges", 2),
                max_grafts=params.get("max_grafts", 1),
            )
        return self.layer.run_all_primitives()
