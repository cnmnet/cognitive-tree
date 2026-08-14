#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from governance.config import Config
from external.providers.arxiv_provider import ArxivProvider
from external.providers.baidu_qianfan import BaiduQianfanProvider
from external.providers.base import BaseSearchProvider, SearchResult
from external.providers.semantic_scholar import SemanticScholarProvider


class SearchPipeline:
    """
    统一外部搜索管道：
    - 多 Provider 按优先级（百度千帆 > arXiv > Semantic Scholar）调用
    - 结果统一为 SearchResult，指纹去重
    - 按 query+provider 做 12 小时 JSON 缓存
    """

    def __init__(self, log_callback: Optional[Callable] = None, cache_ttl_hours: int = 12):
        self.log_callback = log_callback
        self.cache_ttl_hours = cache_ttl_hours

    def _log(self, msg: str, level: str = "system") -> None:
        if self.log_callback:
            self.log_callback(msg, level)

    @property
    def cache_path(self):
        return Config.DATA_ROOT / "系统日志" / "provider_search_cache.json"

    def _load_cache(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self, cache: Dict[str, Any]) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except Exception as e:
            self._log(f"搜索缓存写入失败: {e}", "warning")

    def _fresh(self, entry: Dict[str, Any]) -> bool:
        fetched_at = entry.get("fetched_at") or ""
        try:
            fetched = datetime.fromisoformat(fetched_at)
        except Exception:
            return False
        return datetime.now() - fetched < timedelta(hours=self.cache_ttl_hours)

    def default_providers(self) -> List[BaseSearchProvider]:
        return [
            BaiduQianfanProvider(log_callback=self.log_callback),
            ArxivProvider(log_callback=self.log_callback),
            SemanticScholarProvider(log_callback=self.log_callback),
        ]

    @staticmethod
    def _translated_query(query: str) -> str:
        """论文类源用英文搜索；中文 query 通过 MyMemory 免费翻译。"""
        if not re.search(r"[\u4e00-\u9fff]", query):
            return query
        try:
            import requests
            resp = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": query, "langpair": "zh|en", "de": "a@b.c"},
                timeout=10,
            )
            if resp.status_code == 200:
                translated = resp.json().get("responseData", {}).get("translatedText", "")
                if translated and translated != query:
                    return translated
        except Exception:
            pass
        return query

    def search(self, query: str, top_k: int = 5, providers: Optional[List[BaseSearchProvider]] = None,
               force: bool = False, timeout_per_source: Optional[float] = None,
               total_timeout: Optional[float] = None) -> List[SearchResult]:
        query = (query or "").strip()
        if not query:
            return []
        raw = self._stage_search(query, top_k, providers, force, timeout_per_source, total_timeout)
        # fetch 阶段：当前透传原始结果，后续可在此增强正文
        normalized = self._stage_normalize(raw)
        return self._merge(normalized, top_k)

    def _stage_search(self, query: str, top_k: int,
                      providers: Optional[List[BaseSearchProvider]],
                      force: bool, timeout_per_source: Optional[float],
                      total_timeout: Optional[float]) -> List[SearchResult]:
        """阶段 search：调用各 Provider 并走缓存，返回原始结果。"""
        providers = providers or self.default_providers()
        cache = self._load_cache()
        all_results: List[SearchResult] = []
        now = datetime.now().isoformat(timespec="seconds")
        deadline = time.monotonic() + float(total_timeout or Config.SEARCH_TOTAL_TIMEOUT_SECONDS)

        for provider in providers:
            if time.monotonic() >= deadline:
                self._log("[总超时] 搜索总预算已用尽，跳过剩余搜索源", "warning")
                break
            if not provider.is_available():
                self._log(f"跳过搜索源 {provider.name}（未配置 API Key）", "system")
                continue
            cache_key = hashlib.sha1(f"{query}|{provider.name}".encode("utf-8")).hexdigest()
            entry = cache.get(cache_key)
            if not force and entry and self._fresh(entry):
                for item in entry.get("results", []):
                    try:
                        all_results.append(SearchResult(**item))
                    except Exception:
                        continue
                self._log(f"[缓存命中] {provider.name}: {query[:40]}", "system")
                continue
            try:
                effective_query = query
                if provider.name in ("arxiv", "semantic_scholar"):
                    effective_query = self._translated_query(query)
                timeout_value = Config.SEARCH_PROVIDER_TIMEOUTS.get(provider.name)
                if isinstance(timeout_value, (tuple, list)):
                    per_source = timeout_per_source or float(max(int(v) for v in timeout_value))
                else:
                    per_source = timeout_per_source or float(timeout_value or 30)
                results = self._search_with_timeout(
                    provider,
                    effective_query,
                    min(max(top_k, 1), 10),
                    per_source,
                )
            except Exception as e:
                self._log(f"[搜索失败] {provider.name}: {e}", "warning")
                continue
            cache[cache_key] = {
                "results": [r.to_dict() for r in results],
                "fetched_at": now,
            }
            self._log(f"[搜索完成] {provider.name}: {len(results)} 条（{query[:40]}）", "system")
            all_results.extend(results)

        self._save_cache(cache)
        return all_results

    def _stage_normalize(self, results: List[SearchResult]) -> List[SearchResult]:
        """阶段 clean+filter：清理空标题/URL，剔除占位/模拟标题。"""
        cleaned: List[SearchResult] = []
        for result in results:
            title = (result.title or "").strip()
            url = (result.url or "").strip()
            if not title or not url:
                continue
            if title.startswith(("(", "（")) or "模拟" in title:
                continue
            result.title = title[:120]
            result.url = url
            cleaned.append(result)
        return cleaned

    def _search_with_timeout(self, provider: BaseSearchProvider, query: str,
                             top_k: int, timeout: float) -> List[SearchResult]:
        """在守护线程中执行单源搜索，超时返回空且不影响其它源。"""
        box: Dict[str, Any] = {}

        def _run() -> None:
            try:
                box["results"] = provider.search(query, top_k=top_k)
            except Exception as e:
                box["error"] = e

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout=timeout)
        if worker.is_alive():
            self._log(f"[搜索超时] {provider.name}: 超过 {timeout:.0f}s", "warning")
            return []
        if "error" in box:
            raise box["error"]
        return box.get("results", [])

    @staticmethod
    def _merge(results: List[SearchResult], top_k: int) -> List[SearchResult]:
        seen = set()
        merged: List[SearchResult] = []
        for result in results:
            fingerprint = result.fingerprint or SearchResult.fingerprint_of(result.title, result.url)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            result.fingerprint = fingerprint
            merged.append(result)
        return merged[: max(top_k, 1)]

    def fetch_url(self, url: str, timeout: int = 25) -> str:
        """通过 Jina Reader 抓取网页正文（可选增强，失败返回空）。"""
        if not url:
            return ""
        try:
            import requests
            resp = requests.get(
                Config.JINA_READER_URL + url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout,
            )
            if resp.status_code == 200 and len(resp.text) > 200:
                return resp.text[:2000]
        except Exception as e:
            self._log(f"Jina Reader 抓取失败: {e}", "warning")
        return ""
