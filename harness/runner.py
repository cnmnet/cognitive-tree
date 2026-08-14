"""DAG flow runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from core.interfaces import FlowDefinition
from core.registry import ProcessorRegistry


def load_flows(config_dir: Path) -> Dict[str, FlowDefinition]:
    path = Path(config_dir) / "harness_flows.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    flows: Dict[str, FlowDefinition] = {}
    for flow_id, data in raw.get("flows", {}).items():
        flows[flow_id] = FlowDefinition.from_dict(flow_id, data)
    return flows


class HarnessRunner:
    def __init__(self, registry: ProcessorRegistry) -> None:
        self.registry = registry

    def run(
        self,
        flow: FlowDefinition,
        initial_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        context = dict(initial_context or {})
        done: Dict[str, Any] = {}
        pending: List[Any] = list(flow.steps)
        guard = 0
        while pending:
            guard += 1
            if guard > max(1, len(flow.steps)) * 10:
                raise RuntimeError("flow dependency cycle or unresolved step")
            progressed = False
            for step in list(pending):
                if all(dep in done for dep in step.depends_on):
                    processor = self.registry.get(step.processor)
                    step_context = {**context, **done}
                    result = processor.process(step_context, **step.params)
                    done[step.id] = result
                    pending.remove(step)
                    progressed = True
            if not progressed:
                missing = {
                    s.id: [d for d in s.depends_on if d not in done]
                    for s in pending
                }
                raise RuntimeError(f"unresolved dependencies: {missing}")
        return done
