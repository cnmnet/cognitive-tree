"""access 工厂：创建 GUI/Web 需要的后端对象。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional

from data.storage import DBManager, FileIO
from evolution.meta_layer import MetaLayer
from external.ai_client import AIClient
from external.fetcher import ExternalFetcher
from harness.assurance.anti_fraud import (
    AIPersonaDetector,
    CrossLingualAuditor,
    StarlinkFingerprintDB,
)
from harness.engine import CrystalEngine
from harness.force_explorer import ForceExplorer
from harness.processors.batch_processor import BatchProcessor
from harness.processors.planner import DailyPlanner
from harness.strategy import HebbianStrategy, RUMADStrategy
from evolution.strategy import GodelStrategy, MetaStrategy


def _build_meta_dependencies() -> tuple:
    def force_explorer_factory(engine, log, ai):
        return ForceExplorer(engine, log_callback=log, ai_client=ai)

    providers = SimpleNamespace(
        AIPersonaDetector=AIPersonaDetector,
        StarlinkFingerprintDB=StarlinkFingerprintDB,
        CrossLingualAuditor=CrossLingualAuditor,
    )

    def planner_factory(engine, ai):
        return DailyPlanner(
            engine,
            ai,
            ExternalFetcher(file_io=FileIO),
            lambda m, l="system": print(f"[{l}] {m}"),
            lambda m: print(f"[status] {m}"),
        )

    return force_explorer_factory, providers, planner_factory


def build_evolution_strategies(engine: Any, meta_layer: Any = None,
                               rumad: Any = None, godel: Any = None) -> list:
    """组装可注入的进化策略集合；默认行为由各策略内部实现保持。"""
    strategies = []
    if godel is not None:
        strategies.append(GodelStrategy(godel))
    if meta_layer is not None:
        strategies.append(MetaStrategy(meta_layer))
    if rumad is not None:
        strategies.append(RUMADStrategy(rumad))
    strategies.append(HebbianStrategy(engine))
    return strategies


def create_web_backend() -> Dict[str, Any]:
    """创建 Web 启动时需要的后端对象，保持原有初始化顺序。"""
    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    db = DBManager()
    files = FileIO()
    ai_client = AIClient()
    engine = CrystalEngine(files, ai_client=ai_client)
    force_factory, providers, planner_factory = _build_meta_dependencies()
    engine.meta = MetaLayer(
        engine,
        files,
        ai_client=ai_client,
        force_explorer_factory=force_factory,
        anti_fraud_providers=providers,
        planner_factory=planner_factory,
    )
    return {
        "db": db,
        "files": files,
        "ai_client": ai_client,
        "engine": engine,
    }


def create_gui_backend(log: Optional[Callable] = None) -> Dict[str, Any]:
    """创建 GUI 初始化时需要的后端对象，保持原有初始化顺序。"""
    files = FileIO()
    db = DBManager()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    force_factory, providers, planner_factory = _build_meta_dependencies()
    engine.meta = MetaLayer(
        engine,
        files,
        ai_client=ai,
        force_explorer_factory=force_factory,
        anti_fraud_providers=providers,
        planner_factory=planner_factory,
    )
    engine.start_audit_service()
    if log is not None:
        engine.cheap_gate.log = log
    fetcher = ExternalFetcher(log, FileIO)
    batch_processor = BatchProcessor(ai, log)
    return {
        "files": files,
        "db": db,
        "ai": ai,
        "engine": engine,
        "fetcher": fetcher,
        "batch_processor": batch_processor,
    }
