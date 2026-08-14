"""外部世界服务：搜索、抓取、向量库与外部信息管道。"""

from __future__ import annotations

import re
import requests
from typing import Any, Dict, List


def search_documents(
    search_service: Any,
    keyword: str,
    dirs: List[str],
    regex: bool,
) -> Dict[str, Any]:
    results = search_service.search_documents(keyword, dirs, regex=regex)
    return {
        "results": [
            {"file": f, "line": n, "text": line}
            for f, n, line in results[:500]
        ],
        "total": len(results),
    }


def extract_keywords(text: str) -> List[str]:
    words = re.findall(r"[\w\u4e00-\u9fff]+", text)
    stop = {
        "的",
        "了",
        "和",
        "与",
        "或",
        "一个",
        "这个",
        "那个",
        "如何",
        "什么",
        "为什么",
    }
    return [w for w in words if w not in stop][:5] or ["晶体树", "认知"]


def sync_vector_store(engine: Any) -> Dict[str, Any]:
    try:
        return engine.sync_vector_store()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_trending(engine: Any, limit: int = 10) -> Dict[str, Any]:
    try:
        return {"status": "success", "crystals": engine.get_github_trending_crystals(limit)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def refresh_trending(engine: Any, max_items: int = 10) -> Dict[str, Any]:
    try:
        return engine.run_github_trending_daily(max_items)
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_radar(fetcher_factory: Any) -> Dict[str, Any]:
    try:
        fetcher = fetcher_factory()
        return {
            "status": "success",
            "data": fetcher.fetch_multilingual_news(max_per_lang=5),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def vector_status(engine: Any) -> Dict[str, Any]:
    try:
        return {
            "available": engine.vector_store.is_available(),
            "count": engine.vector_store.count(),
        }
    except Exception as e:
        return {"available": False, "count": 0, "error": str(e)}


def get_conflicts(engine: Any, method: str = "auto", limit: int = 20) -> Dict[str, Any]:
    try:
        scope = engine.get_conflict_scope()
        conflicts = engine.detect_conflicts(scope=scope, method=method)
        if limit > 0:
            conflicts = conflicts[:limit]
        return {
            "total": len(conflicts),
            "conflicts": [
                {
                    "crystal_a": c.crystal_a,
                    "crystal_b": c.crystal_b,
                    "similarity": c.similarity,
                    "content_a": c.content_a,
                    "content_b": c.content_b,
                }
                for c in conflicts
            ],
        }
    except Exception as e:
        return {"error": str(e), "conflicts": []}


def duckduckgo_search(
    keywords: List[str],
    requests_available: bool,
    user_agent_factory: Any,
) -> str:
    """DuckDuckGo 文本搜索，失败时返回可读错误。"""
    if not requests_available:
        return "需要安装 requests 库"
    query = " ".join(keywords)
    headers = {"User-Agent": user_agent_factory()}
    url = "https://html.duckduckgo.com/html/"
    try:
        resp = requests.post(url, data={"q": query}, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text
        results = []
        titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html)
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html)
        for i in range(min(3, len(titles), len(snippets))):
            title = re.sub(r"<[^>]+>", "", titles[i]).strip()
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            results.append(f"- {title}: {snippet[:150]}...")
        return "\n".join(results) if results else "未找到相关结果"
    except Exception as e:
        return f"搜索出错: {str(e)}"


def run_external_fetch(
    fetcher_factory: Any,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        fetcher = fetcher_factory()
        sources = ["arxiv", "huggingface", "news"]
        queries = ["cat:cs.AI", None, "大模型 进展"]
        result = fetcher.fetch_and_store(sources, queries)
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()


def run_sync_vector_store(
    engine: Any,
    on_log: Any,
    on_done: Any,
) -> None:
    """同步向量库并通过回调汇报结果。"""
    try:
        result = engine.sync_vector_store()
        if result["status"] == "already_synced":
            on_log(f"✅ 向量库已同步（{result['total']} 条晶体）", "success")
        elif result["status"] == "synced":
            on_log(
                f"✅ 向量库同步完成：{result['synced']}/{result['total']} 条晶体",
                "success",
            )
        else:
            on_log(f"⚠️ 同步失败：{result.get('status', 'unknown')}", "warning")
    except Exception as e:
        on_log(f"❌ 同步出错：{e}", "error")
    on_done()
