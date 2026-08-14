"""Built-in processors."""

from .debate import DebateContext, DebateEngine, DebateRole
from .planner import BaselineRunner, DailyPlanner
from .batch_processor import BatchProcessor
from .dag_demo import (
    BaselineProcessor,
    DebateProcessor,
    PlannerProcessor,
    ReportProcessor,
    RetrievalProcessor,
)


def register_default_processors(registry) -> None:
    for processor in [
        BaselineProcessor(),
        RetrievalProcessor(),
        DebateProcessor(),
        ReportProcessor(),
        PlannerProcessor(),
    ]:
        registry.register(processor)


__all__ = [
    "BaselineProcessor",
    "BaselineRunner",
    "BatchProcessor",
    "DailyPlanner",
    "DebateContext",
    "DebateEngine",
    "DebateProcessor",
    "DebateRole",
    "PlannerProcessor",
    "ReportProcessor",
    "RetrievalProcessor",
    "register_default_processors",
]
