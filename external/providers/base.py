#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SearchResult:
    """外部搜索结果的统一结构。"""

    source: str
    title: str
    url: str = ""
    content: str = ""
    published_at: str = ""
    relevance: float = 0.0
    fingerprint: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "published_at": self.published_at,
            "relevance": round(self.relevance, 3),
            "fingerprint": self.fingerprint,
        }

    @staticmethod
    def fingerprint_of(title: str, url: str = "") -> str:
        normalized = re.sub(r"[\s\u3000]+", "", (title or "").lower())
        return hashlib.sha1(f"{normalized}|{url or ''}".encode("utf-8")).hexdigest()[:16]


class BaseSearchProvider:
    """搜索 Provider 基类：子类实现 search()，统一返回 SearchResult。"""

    name: str = "base"

    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback

    def _log(self, msg: str, level: str = "warning") -> None:
        if self.log_callback:
            self.log_callback(msg, level)

    def is_available(self) -> bool:
        return True

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        raise NotImplementedError
