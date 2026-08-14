#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from governance.config import Config
from external.providers.base import BaseSearchProvider, SearchResult


class BaiduQianfanProvider(BaseSearchProvider):
    """
    百度千帆 AI 搜索 Provider。

    优先调用 /v2/ai_search/web_summary（智能搜索生成高性能版，每日 100 次免费）；
    失败或 401/403 时降级到 /v2/ai_search/chat/completions，并尝试 AppBuilder 鉴权头。
    """

    name = "baidu_qianfan"

    def __init__(self, api_key: str = "", appbuilder_key: str = "",
                 log_callback: Optional[Any] = None):
        super().__init__(log_callback=log_callback)
        self.api_key = api_key or Config.BAIDU_API_KEY
        self.appbuilder_key = appbuilder_key or Config.BAIDU_APPBUILDER_API_KEY

    def is_available(self) -> bool:
        return bool(self.api_key or self.appbuilder_key)

    def _headers(self, use_appbuilder: bool = False) -> Dict[str, str]:
        key = self.appbuilder_key if use_appbuilder else self.api_key
        header = "X-Appbuilder-Authorization" if use_appbuilder else "Authorization"
        return {
            header: f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _post(self, url: str, body: Dict[str, Any], use_appbuilder: bool = False) -> Dict[str, Any]:
        try:
            import time
        except ImportError:
            time = None
        last_error = None
        for attempt in range(2):
            try:
                import requests
                resp = requests.post(
                    url,
                    headers=self._headers(use_appbuilder=use_appbuilder),
                    json=body,
                    timeout=Config.QIANFAN_TIMEOUT,
                )
                if resp.status_code == 200:
                    return resp.json() or {}
                if resp.status_code in (401, 403) and not use_appbuilder and self.appbuilder_key:
                    return self._post(url, body, use_appbuilder=True)
                self._log(f"百度千帆返回 {resp.status_code}: {resp.text[:120]}", "warning")
                return {}
            except Exception as e:
                last_error = e
                if attempt == 0:
                    self._log(f"百度千帆请求失败，重试一次: {e}", "warning")
                    if time is not None:
                        try:
                            time.sleep(0.5)
                        except Exception:
                            pass
        self._log(f"百度千帆请求失败: {last_error}", "warning")
        return {}

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        if not self.is_available():
            return []
        body = {
            "messages": [{"role": "user", "content": query}],
            "stream": False,
            "resource_type_filter": [{"type": "web", "top_k": min(max(top_k, 1), 20)}],
        }
        data = self._post(Config.BAIDU_SEARCH_API_URL, body)
        if not data:
            chat_body = dict(body)
            chat_body["model"] = "ernie-3.5-8k"
            data = self._post(Config.BAIDU_SEARCH_CHAT_URL, chat_body)
        return self.parse_response(data, query=query, top_k=top_k)

    @staticmethod
    def parse_response(data: Dict[str, Any], query: str = "", top_k: int = 5) -> List[SearchResult]:
        """把百度千帆 web_summary / chat.completions 响应解析为统一 SearchResult。"""
        results: List[SearchResult] = []
        references = data.get("references") or []
        for ref in references:
            title = (ref.get("title") or "").strip()
            url = (ref.get("url") or "").strip()
            content = (ref.get("content") or ref.get("snippet") or "").strip()
            if not title or not url:
                continue
            result = SearchResult(
                source="百度千帆",
                title=title[:120],
                url=url,
                content=content[:600],
                published_at=(ref.get("date") or "")[:19],
                fingerprint=SearchResult.fingerprint_of(title, url),
            )
            result.raw = {
                "website": ref.get("website") or "",
                "rerank_score": ref.get("rerank_score"),
                "authority_score": ref.get("authority_score"),
                "query": query,
            }
            results.append(result)
        return results[: max(top_k, 1)]
