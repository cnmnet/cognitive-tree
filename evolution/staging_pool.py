"""Staging pool: inner/outer loop buffer for evolution drafts."""

from __future__ import annotations

import time
from typing import Any, Dict, List


class StagingPool:
    def __init__(self, ttl_seconds: float = 3600.0, max_size: int = 500) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._drafts: Dict[str, Dict[str, Any]] = {}

    def submit(self, draft: Dict[str, Any]) -> str:
        draft_id = str(draft.get("id") or f"draft-{len(self._drafts) + 1}")
        self._drafts[draft_id] = {
            "draft": draft,
            "submitted_at": time.time(),
        }
        if len(self._drafts) > self.max_size:
            self._evict_oldest()
        return draft_id

    def conflict_check(self, draft: Dict[str, Any]) -> bool:
        target = draft.get("target")
        for entry in self._drafts.values():
            if entry["draft"].get("target") == target:
                return True
        return False

    def fetch_candidates(self, limit: int = 5) -> List[Dict[str, Any]]:
        now = time.time()
        expired = [k for k, v in self._drafts.items() if now - v["submitted_at"] > self.ttl_seconds]
        for key in expired:
            self._drafts.pop(key, None)
        candidates = [entry["draft"] for entry in self._drafts.values()]
        return candidates[:limit]

    def _evict_oldest(self) -> None:
        oldest = min(self._drafts, key=lambda k: self._drafts[k]["submitted_at"])
        self._drafts.pop(oldest, None)
