"""access 唯一的实现依赖出口：其他 access 文件禁止直接 import 底层实现。"""

from __future__ import annotations

from core.dependencies import REQUESTS_AVAILABLE as REQUESTS_AVAILABLE
from core.registry import ProcessorRegistry as ProcessorRegistry
from core.text_utils import normalize_text as normalize_text
from data.storage import FileIO as FileIO, HealthChecker as HealthChecker
from external.ai_client import (
    AIClient as AIClient,
    fallback_session_title as fallback_session_title,
    generate_session_title_from_content as generate_session_title_from_content,
)
from external.fetcher import ExternalFetcher as ExternalFetcher
from external.network import NetworkManager as NetworkManager
from external.search import SearchService as SearchService
from governance.config import Config as Config
from harness.processors import register_default_processors as register_default_processors
from harness.processors.batch_processor import BatchProcessor as BatchProcessor
from harness.processors.debate import DebateEngine as DebateEngine
from harness.processors.planner import DailyPlanner as DailyPlanner
from harness.reporting import (
    ORIGINAL_REPORT_TARGET as ORIGINAL_REPORT_TARGET,
    QUICK_VIEW_TARGET as QUICK_VIEW_TARGET,
    build_debate_report_markdown as build_debate_report_markdown,
    build_quick_view_report as build_quick_view_report,
    limit_original_report as limit_original_report,
)
from harness.runner import HarnessRunner as HarnessRunner, load_flows as load_flows

__all__ = [
    "REQUESTS_AVAILABLE",
    "ProcessorRegistry",
    "normalize_text",
    "FileIO",
    "HealthChecker",
    "AIClient",
    "fallback_session_title",
    "generate_session_title_from_content",
    "ExternalFetcher",
    "NetworkManager",
    "SearchService",
    "Config",
    "register_default_processors",
    "BatchProcessor",
    "DebateEngine",
    "DailyPlanner",
    "ORIGINAL_REPORT_TARGET",
    "QUICK_VIEW_TARGET",
    "build_debate_report_markdown",
    "build_quick_view_report",
    "limit_original_report",
    "HarnessRunner",
    "load_flows",
]
