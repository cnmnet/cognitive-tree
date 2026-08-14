"""Fast loop: low-cost offline screening of evolution drafts."""

from __future__ import annotations

import time
from typing import Any, Dict


class FastLoop:
    def __init__(self, min_score: float = 65.0, max_duration_seconds: float = 2.0) -> None:
        self.min_score = min_score
        self.max_duration_seconds = max_duration_seconds

    def evaluate(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        score = float(draft.get("score", 0.0))
        passed = score >= self.min_score and (time.time() - start) <= self.max_duration_seconds
        return {
            "passed": passed,
            "score": score,
            "reason": "fast loop passed" if passed else "fast loop rejected",
        }
