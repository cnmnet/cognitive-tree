"""Core contracts, models and persistence."""

from .benchmarks import BENCHMARK_QUESTIONS
from .fingerprint import FingerprintExtractor
from .interfaces import EvolutionStrategy, FlowDefinition, FlowStep, IProcessor
from .models import CognitiveFingerprint, Crystal, HealthCheckResult, Hole, Report
from .persistence import JSONPatch, PatchStore
from .registry import ProcessorRegistry

__all__ = [
    "BENCHMARK_QUESTIONS",
    "CognitiveFingerprint",
    "Crystal",
    "EvolutionStrategy",
    "FingerprintExtractor",
    "FlowDefinition",
    "FlowStep",
    "HealthCheckResult",
    "Hole",
    "IProcessor",
    "JSONPatch",
    "PatchStore",
    "ProcessorRegistry",
    "Report",
]
