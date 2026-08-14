"""External interfaces and addon ecosystem."""

from .ai_client import AIClient, generate_session_title_from_content
from .fetcher import ExternalFetcher
from .network import NetworkManager
from .search import SearchService

__all__ = [
    "AIClient",
    "ExternalFetcher",
    "NetworkManager",
    "SearchService",
    "generate_session_title_from_content",
]
