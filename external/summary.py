#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""千帆搜索结果本地 NLP 压缩（jieba TextRank 抽取式摘要）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List

import jieba.analyse


EVIDENCE_REF_RE = re.compile(
    r"(\[C\d+\]|\[H\d+\]|\[E\d+\]|\[arxiv\]|\[news\]|\[hf\]|\[external\])",
    re.IGNORECASE,
)
KEY_SECTION_RE = re.compile(
    r"(结论|核心|决策|风险|下一步|建议|方案|依据|靶向|辩护|吸收|终选|裁决|证据|预算|资源|目标|执行)"
)
DATE_RE = re.compile(r"(202[0-9]年|202[0-9]-\d{1,2}-\d{1,2}|\d{1,2}月\d{1,2}日)")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|元|万|亿|天|小时|分钟|年|月|日|倍|美元)")


def summarize_text(content: str, target_chars: int = 100) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])", content) if s.strip()]
    if not sentences:
        return content[:target_chars]
    keywords = set(jieba.analyse.textrank(content, topK=10, withWeight=False))

    def score(sentence: str, index: int) -> float:
        length = len(sentence)
        if length < 8 or length > 200:
            return -1
        hits = sum(1 for kw in keywords if kw in sentence)
        bonus = 0.0
        if DATE_RE.search(sentence):
            bonus += 1.5
        if NUMBER_RE.search(sentence):
            bonus += 1.0
        return hits * 2 + (1 if index == 0 else 0) + min(1.0, length / 120) + bonus

    ranked = sorted(
        enumerate(sentences),
        key=lambda pair: score(pair[1], pair[0]),
        reverse=True,
    )
    picked = set()
    total = 0
    for idx, sentence in ranked:
        if total + len(sentence) > target_chars:
            continue
        picked.add(idx)
        total += len(sentence)
        if total >= target_chars:
            break
    return "".join(sentences[i] for i in sorted(picked)) or content[:target_chars]


def extract_keywords(text: str, top_k: int = 8) -> List[str]:
    """用 jieba TextRank 抽取中文关键词（千帆查询词本地降级用）。"""
    try:
        words = jieba.analyse.textrank(text, topK=top_k, withWeight=False)
    except Exception:
        words = []
    return [w.strip() for w in words if w and w.strip()]


def summarize_role_answer(answer: str, target_chars: int = 1500) -> str:
    """压缩单个角色的轮次发言，优先保留开篇结论、证据引用和关键段落。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", answer) if p.strip()]
    if not paragraphs:
        return answer[:target_chars]
    if sum(len(p) for p in paragraphs) <= target_chars:
        return answer.strip()

    first_budget = min(len(paragraphs[0]), max(300, int(target_chars * 0.3)))
    kept = [paragraphs[0][:first_budget]]
    kept_idx = {0}
    used = len(kept[0])
    for idx in range(1, len(paragraphs)):
        if used >= target_chars:
            break
        para = paragraphs[idx]
        if EVIDENCE_REF_RE.search(para) or KEY_SECTION_RE.search(para):
            if used + len(para) > target_chars:
                para = para[: target_chars - used]
            kept.append(para)
            kept_idx.add(idx)
            used += len(para)
    if used < target_chars:
        for idx in range(1, len(paragraphs)):
            if idx in kept_idx or used >= target_chars:
                continue
            para = paragraphs[idx]
            if used + len(para) > target_chars:
                para = para[: target_chars - used]
            kept.append(para)
            kept_idx.add(idx)
            used += len(para)
    result = "\n\n".join(kept)
    return result[:target_chars] if len(result) > target_chars else result


def summarize_items(
    items: List[Dict[str, Any]],
    max_items: int = 5,
    per_item_chars: int = 150,
) -> List[Dict[str, Any]]:
    seen = set()
    candidates = []
    for item in items:
        title = (item.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        content = item.get("summary") or item.get("content") or ""
        richness = (
            2 * (1 if DATE_RE.search(content) else 0)
            + 2 * (1 if NUMBER_RE.search(content) else 0)
            + 1 * (1 if (item.get("link") or item.get("url")) else 0)
            + min(1.0, len(content) / 200)
        )
        candidates.append((richness, len(candidates), item))
    candidates.sort(key=lambda entry: (-entry[0], entry[1]))
    selected = candidates[:max_items]
    selected.sort(key=lambda entry: entry[1])
    result = []
    for _, _, item in selected:
        result.append(
            {
                "title": (item.get("title") or "").strip()[:120],
                "summary": summarize_text(item.get("summary") or item.get("content") or "", per_item_chars),
                "link": item.get("link") or item.get("url") or "",
            }
        )
    return result
