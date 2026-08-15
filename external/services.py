"""外部世界服务：搜索、抓取、向量库与外部信息管道。"""

from __future__ import annotations

import re
import requests
from typing import Any, Dict, List

from external.ai_client import AIClient
from governance.config import Config


COGNITIVE_DIMENSION_LABELS = {
    "zh_CN": [
        ("knowledge_lifecycle", "知识生命周期意识"),
        ("human_ai_collaboration_reconstruction", "人机协同机制重构"),
        ("cognitive_domestication_awareness", "认知驯化风险与独立思想"),
        ("tree_decomposition_potential", "树形拆解潜力"),
        ("long_term_asset_irreplaceability", "长期资产与不可替代性"),
        ("hidden_trap_detection", "隐性陷阱识别"),
    ],
    "en_US": [
        ("knowledge_lifecycle", "Knowledge Lifecycle Awareness"),
        ("human_ai_collaboration_reconstruction", "Human-AI Collaboration Reconstruction"),
        ("cognitive_domestication_awareness", "Cognitive Domestication Awareness"),
        ("tree_decomposition_potential", "Tree Decomposition Potential"),
        ("long_term_asset_irreplaceability", "Long-Term Asset and Irreplaceability"),
        ("hidden_trap_detection", "Hidden Trap Detection"),
    ],
}

SURPRISE_TAGS = {
    "counterintuitive": "反常识",
    "opportunity_window": "机会窗口",
    "asymmetric_payoff": "非对称收益",
}


def _cognitive_prompt(text: str, lang: str) -> str:
    labels = COGNITIVE_DIMENSION_LABELS.get(lang, COGNITIVE_DIMENSION_LABELS["zh_CN"])
    dimensions = "\n".join(f"- {key}: {label} (0-100)" for key, label in labels)
    return (
        "你是认知晶体树的认知层级评审员。请只返回 JSON，不要输出解释。\n"
        "评分维度：\n"
        f"{dimensions}\n"
        "- surprise_winning: 出奇制胜（0-100），并给出反常识 counterintuitive、"
        "机会窗口 opportunity_window、非对称收益 asymmetric_payoff 三个子分（0-100）\n"
        "JSON schema：\n"
        '{"dimensions": {"knowledge_lifecycle": 0, '
        '"human_ai_collaboration_reconstruction": 0, '
        '"cognitive_domestication_awareness": 0, '
        '"tree_decomposition_potential": 0, '
        '"long_term_asset_irreplaceability": 0, '
        '"hidden_trap_detection": 0}, '
        '"surprise_winning": {"score": 0, '
        '"sub_scores": {"counterintuitive": 0, '
        '"opportunity_window": 0, "asymmetric_payoff": 0}, '
        '"evidence": "..."}}\n'
        "评分依据必须引用报告原句或核心概念。\n\n"
        f"报告文本：\n{text[:12000]}"
    )


def _normalize_cognitive_result(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    dims = data.get("dimensions")
    if not isinstance(dims, dict):
        return None
    base_keys = [key for key, _ in COGNITIVE_DIMENSION_LABELS["zh_CN"]]
    if any(not isinstance(dims.get(key), (int, float)) for key in base_keys):
        return None
    surprise = data.get("surprise_winning")
    if not isinstance(surprise, dict):
        return None
    sub = surprise.get("sub_scores")
    if not isinstance(sub, dict):
        return None
    sub_keys = ("counterintuitive", "opportunity_window", "asymmetric_payoff")
    if any(not isinstance(sub.get(key), (int, float)) for key in sub_keys):
        return None
    surprise_score = round(
        0.4 * float(sub["counterintuitive"])
        + 0.3 * float(sub["opportunity_window"])
        + 0.3 * float(sub["asymmetric_payoff"]),
        1,
    )
    base_avg = sum(float(dims[key]) for key in base_keys) / len(base_keys)
    weighted_total = round(0.75 * base_avg + 0.25 * surprise_score, 1)
    if weighted_total >= 90:
        level = "deep"
    elif weighted_total >= 80:
        level = "structured"
    elif weighted_total >= 70:
        level = "experience_structured"
    else:
        level = "summary"
    return {
        "dimensions": {key: round(float(dims[key]), 1) for key in base_keys},
        "surprise_winning": {
            "score": surprise_score,
            "sub_scores": {key: round(float(sub[key]), 1) for key in sub_keys},
            "evidence": str(surprise.get("evidence", ""))[:200],
        },
        "weighted_total": weighted_total,
        "cognitive_level": level,
        "strategy_tags": [
            SURPRISE_TAGS[key] for key in sub_keys if float(sub[key]) >= 80
        ],
    }


def _pending_cognitive() -> Dict[str, Any]:
    return {
        "method": "llm_assisted",
        "dimensions": {},
        "surprise_winning": {
            "score": None,
            "sub_scores": {},
            "evidence": "",
        },
        "weighted_total": None,
        "cognitive_level": None,
        "strategy_tags": [],
        "status": "pending_llm",
    }


def score_cognitive_level(
    text: str,
    ai_client: Any = None,
    lang: str = "zh_CN",
) -> Dict[str, Any]:
    if ai_client is None:
        ai_client = AIClient(api_key=Config.get_api_key())
    last_error = ""
    for _ in range(2):
        try:
            raw = ai_client.chat_json(_cognitive_prompt(text, lang), temperature=0.2)
        except Exception as exc:
            last_error = str(exc)
            raw = {"error": last_error}
        if isinstance(raw, dict) and "error" in raw:
            last_error = str(raw.get("error", ""))
            continue
        normalized = _normalize_cognitive_result(raw)
        if normalized is not None:
            normalized["method"] = "llm_assisted"
            normalized["status"] = "scored"
            return normalized
        last_error = "invalid cognitive score schema"
    result = _pending_cognitive()
    result["error"] = last_error[:200]
    return result


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
