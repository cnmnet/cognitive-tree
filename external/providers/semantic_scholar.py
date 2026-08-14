#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List

from governance.config import Config
from external.providers.base import BaseSearchProvider, SearchResult


class SemanticScholarProvider(BaseSearchProvider):
    """Semantic Scholar 免费论文搜索（无 Key）。"""

    name = "semantic_scholar"
    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        try:
            import requests
            resp = requests.get(
                self.API_URL,
                params={
                    "query": query,
                    "limit": min(max(top_k, 1), 10),
                    "fields": "title,abstract,year,url,externalIds",
                },
                timeout=Config.SEARCH_PROVIDER_TIMEOUTS.get(
                    "semantic_scholar",
                    (10, 25),
                ),
            )
            if resp.status_code != 200:
                self._log(f"Semantic Scholar 返回 {resp.status_code}", "warning")
                return []
            data = (resp.json() or {}).get("data") or []
            results = []
            for item in data:
                title = (item.get("title") or "").strip()
                url = (item.get("url") or "").strip()
                if not title:
                    continue
                year = item.get("year")
                results.append(SearchResult(
                    source="Semantic Scholar",
                    title=title[:120],
                    url=url or "",
                    content=(item.get("abstract") or "")[:600],
                    published_at=str(year) if year else "",
                    fingerprint=SearchResult.fingerprint_of(title, url),
                ))
            return results[: max(top_k, 1)]
        except Exception as e:
            self._log(f"Semantic Scholar 请求失败: {e}", "warning")
            return []
