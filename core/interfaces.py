"""Core contracts for the pluggable self-evolving architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class IProcessor(Protocol):
    """A unit of work that can be registered and called by a flow."""

    name: str

    def process(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        ...


@runtime_checkable
class IPatch(Protocol):
    """An atomic, reversible mutation."""

    patch_id: str
    patch_type: str
    target: str

    def apply(self) -> bool:
        ...

    def rollback(self) -> bool:
        ...

    def describe(self) -> str:
        ...


@runtime_checkable
class IPlugin(Protocol):
    """A distributable capability bundle that registers processors and patches."""

    metadata: Dict[str, Any]

    def register(self, registry: Any) -> None:
        ...


@runtime_checkable
class EvolutionStrategy(Protocol):
    """可注入的进化策略：接收上下文，返回结构化结果，默认行为由内部实现保持。"""

    name: str

    def run(self, context: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        ...


@dataclass
class FlowStep:
    id: str
    processor: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class FlowDefinition:
    id: str
    description: str = ""
    steps: List[FlowStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, flow_id: str, data: Dict[str, Any]) -> "FlowDefinition":
        steps = []
        for item in data.get("steps", []):
            steps.append(
                FlowStep(
                    id=item["id"],
                    processor=item["processor"],
                    params=item.get("params", {}),
                    depends_on=item.get("depends_on", []),
                )
            )
        return cls(id=flow_id, description=data.get("description", ""), steps=steps)
