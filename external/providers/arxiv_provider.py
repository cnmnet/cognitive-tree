#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List

from external.providers.base import BaseSearchProvider, SearchResult


class ArxivProvider(BaseSearchProvider):
    """arXiv 论文搜索（复用 arxiv 官方库，免费无 Key）。"""

    name = "arxiv"

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        try:
            import arxiv
        except ImportError:
            return []
        try:
            search = arxiv.Search(
                query=query or "cat:cs.AI",
                max_results=min(max(top_k, 1), 10),
                sort_by=arxiv.SortCriterion.Relevance,
            )
            client = arxiv.Client(page_size=min(max(top_k, 1), 10), delay_seconds=1.0)
            results = []
            for paper in client.results(search):
                title = (paper.title or "").replace("\n", " ").strip()
                summary = (paper.summary or "").replace("\n", " ").strip()
                published = paper.published.date().isoformat() if paper.published else ""
                results.append(SearchResult(
                    source="arXiv",
                    title=title[:120],
                    url=paper.entry_id or "",
                    content=summary[:600],
                    published_at=published,
                    fingerprint=SearchResult.fingerprint_of(title, paper.entry_id or ""),
                ))
            return results[: max(top_k, 1)]
        except Exception as e:
            self._log(f"arXiv 请求失败: {e}", "warning")
            return []
