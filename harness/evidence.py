#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from governance.config import Config


@dataclass
class EvidenceItem:
    """单条证据：来源、标题、正文、可核验线索。"""

    evidence_id: str
    source: str
    title: str
    content: str
    url: str = ""
    published_at: str = ""
    relevance: float = 0.0
    fingerprint: str = ""
    category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "published_at": self.published_at,
            "relevance": round(self.relevance, 3),
            "fingerprint": self.fingerprint,
            "category": self.category,
        }

    def format_prompt(self, max_chars: int = 180) -> str:
        content = self.content if len(self.content) <= max_chars else self.content[:max_chars] + "..."
        date_part = f" | {self.published_at}" if self.published_at else ""
        url_part = f" | {self.url}" if self.url else ""
        return f"[{self.evidence_id}] 来源:{self.source}{date_part} | {self.title} | {content}{url_part}"


@dataclass
class EvidencePackage:
    """一次辩论使用的证据包，按相关度排序并编号。"""

    items: List[EvidenceItem] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def format_for_prompt(self, limit: int = 6, max_chars_per_item: int = 180) -> str:
        if not self.items:
            return ""
        lines = ["【证据包（内部与外部已验证资料，引用时使用 [E编号]）】"]
        for item in self.items[:limit]:
            lines.append("- " + item.format_prompt(max_chars_per_item))
        lines.append("")
        lines.append("引用规则：引用上述资料时标注 [E001] 等编号；禁止把证据包之外的事实说成已验证。")
        return "\n".join(lines)

    def summarize(self) -> Dict[str, Any]:
        return {
            "count": len(self.items),
            "keywords": self.keywords,
            "sources": list(dict.fromkeys(i.source for i in self.items)),
            "items": [i.to_dict() for i in self.items],
        }


class EvidenceOrchestrator:
    """
    证据编排器：统一构建、注入、验证证据，形成可审计的证据链。

    事前：从问题关键词检索内部晶体与外部缓存，构建证据包（[E001]...）。
    事中：将证据包注入角色 prompt，要求按编号引用。
    事后：主张验证 + 算术自洽门 + 假设分级 + 可信度报告。
    """

    STOPWORDS = {
        "的", "了", "和", "与", "及", "或", "为", "在", "对", "从", "到", "将", "把",
        "被", "让", "给", "以", "之", "其", "等", "请", "给出", "明确", "如何", "什么",
        "是否", "应该", "可以", "需要", "一个", "一种", "我们", "你们", "他们", "这个",
        "那个", "以及", "进行", "通过", "关于", "问题", "答案", "报告", "输出", "要求",
        "一家", "中型", "面临", "持续", "考虑", "希望", "目标", "当前", "最终", "然后",
    }
    A_MARKERS = ("[arxiv]", "[news]", "[hf]", "[external]", "据", "报告", "研究表明", "数据显示", "统计")
    B_MARKERS = ("预计", "约", "大概", "估计", "通常", "一般")
    C_MARKERS = ("假设", "如果", "可能", "或许", "也许", "待验证", "大概率", "风险在于")

    def __init__(self, engine: Any = None, ai_client: Any = None,
                 log_callback: Any = None, max_items: int = 10):
        self.engine = engine
        self.ai = ai_client
        self._log_callback = log_callback
        self.max_items = max(3, min(20, int(max_items or 10)))

    def _log(self, msg: str, tag: str = "system") -> None:
        if self._log_callback:
            self._log_callback(msg, tag)

    # ==================== 关键词、指纹、相关度 ====================

    def extract_keywords(self, text: str, limit: int = 12) -> List[str]:
        tokens: List[str] = []
        try:
            import jieba
            for segment in re.split(r"([A-Za-z][A-Za-z0-9_\-]{1,}|\d+\.?\d*%?)", text or ""):
                if not segment:
                    continue
                if re.match(r"^[A-Za-z][A-Za-z0-9_\-]{1,}$", segment) or re.match(r"^\d+\.?\d*%?$", segment):
                    tokens.append(segment)
                else:
                    tokens.extend(jieba.lcut(segment))
        except Exception:
            tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,}|\d+\.?\d*%?|[\u4e00-\u9fff]{2,}", text or "")
        counts = Counter(tokens)
        keywords: List[str] = []
        for token, _cnt in counts.most_common():
            t = token.lower()
            if len(t) < 2 or t in self.STOPWORDS:
                continue
            if token in keywords:
                continue
            keywords.append(token)
            if len(keywords) >= limit:
                break
        return keywords

    @staticmethod
    def fingerprint(text: str) -> str:
        normalized = re.sub(r"[\s\u3000，。；：、！？（）《》“”‘’\-_—…\d]+", "", (text or "").lower())
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _relevance(keywords: List[str], text: str) -> float:
        if not keywords or not text:
            return 0.0
        text_lower = text.lower()
        score = 0.0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in text_lower:
                score += 1.0
                continue
            # 中文未分词时，用 2-4 字片段近似匹配，避免整句关键词失配
            grams = [
                kw_lower[i:i + n]
                for n in (2, 3, 4)
                for i in range(max(0, len(kw_lower) - n + 1))
            ]
            if any(len(g) >= 2 and g in text_lower for g in grams):
                score += 0.5
        return min(1.0, score / max(1, len(keywords) * 0.25))

    # ==================== 内部证据 ====================

    def _crystal_evidence(self, question: str, keywords: List[str]) -> List[EvidenceItem]:
        if not self.engine:
            return []
        items: List[EvidenceItem] = []
        try:
            crystals = self.engine.get_associative_crystals(question, top_k=5)
        except Exception:
            crystals = []
        for crystal in crystals:
            content = getattr(crystal, "content", "") or ""
            title = getattr(crystal, "id", "") or getattr(crystal, "title", "") or "晶体"
            text = f"{title} {content}"
            rel = self._relevance(keywords, text)
            if rel <= 0:
                continue
            items.append(EvidenceItem(
                evidence_id="",
                source="晶体库",
                title=title,
                content=content[:300],
                relevance=rel,
                category="internal",
                fingerprint=self.fingerprint(text[:300]),
            ))
        return items

    # ==================== 外部缓存证据 ====================

    def _external_cache_evidence(self, keywords: List[str]) -> List[EvidenceItem]:
        path = Config.DATA_ROOT / Config.PATHS["external_cache"]
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        cache = raw.get("data", raw)
        collected: List[Dict[str, str]] = []

        def walk(obj: Any, source: str = "缓存") -> None:
            if isinstance(obj, dict):
                title = obj.get("title") or obj.get("name") or ""
                content = obj.get("summary") or obj.get("content") or obj.get("description") or ""
                if title and content:
                    collected.append({
                        "source": obj.get("source") or source,
                        "title": str(title),
                        "content": str(content),
                        "url": obj.get("url") or obj.get("link") or "",
                    })
                for value in obj.values():
                    walk(value, source)
            elif isinstance(obj, list):
                for value in obj:
                    walk(value, source)

        walk(cache)
        items: List[EvidenceItem] = []
        seen_titles = set()
        for entry in collected:
            title = entry["title"]
            if "模拟" in title or "(mock" in title.lower() or "mock" in title.lower()[:20]:
                continue
            text = f"{title} {entry['content']}"
            rel = self._relevance(keywords, text)
            if rel <= 0:
                continue
            if title in seen_titles:
                continue
            seen_titles.add(title)
            items.append(EvidenceItem(
                evidence_id="",
                source=entry["source"],
                title=title,
                content=entry["content"][:300],
                url=entry["url"],
                relevance=rel,
                category="external",
                fingerprint=self.fingerprint(text[:300]),
            ))
        return items

    # ==================== 网络证据（可选，默认不阻塞辩论） ====================

    def _network_evidence(self, question: str, keywords: List[str], timeout: int = 12) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        try:
            from external.search_pipeline import SearchPipeline
            pipeline = SearchPipeline(log_callback=self._log)
            queries = [kw for kw in keywords if len(kw) >= 2][:3] or [question]
            for query in queries:
                try:
                    results = pipeline.search(query, top_k=3)
                except Exception:
                    continue
                for result in results:
                    title = result.title or ""
                    if not title or title.startswith("(") or "模拟" in title:
                        continue
                    text = f"{title} {result.content}"
                    items.append(EvidenceItem(
                        evidence_id="",
                        source=result.source,
                        title=title[:120],
                        content=result.content[:300],
                        url=result.url,
                        published_at=result.published_at,
                        relevance=self._relevance(keywords, text),
                        category="external",
                        fingerprint=self.fingerprint(text[:300]),
                    ))
        except Exception as e:
            self._log(f"网络证据抓取失败（不影响辩论）: {e}", "warning")
        return items

    # ==================== 构建证据包 ====================

    def _dedupe(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        seen = set()
        result: List[EvidenceItem] = []
        for item in items:
            fp = item.fingerprint or self.fingerprint(f"{item.title} {item.content}"[:300])
            if fp in seen:
                continue
            seen.add(fp)
            item.fingerprint = fp
            result.append(item)
        return result

    def build_package(self, question: str, max_items: int = None,
                      use_network: bool = False) -> EvidencePackage:
        max_items = max_items or self.max_items
        keywords = self.extract_keywords(question)
        items: List[EvidenceItem] = []
        items.extend(self._crystal_evidence(question, keywords))
        items.extend(self._external_cache_evidence(keywords))
        if use_network:
            items.extend(self._network_evidence(question, keywords))
        items = self._dedupe(items)
        items.sort(key=lambda item: item.relevance, reverse=True)
        for idx, item in enumerate(items, 1):
            item.evidence_id = f"E{idx:03d}"
        package = EvidencePackage(items=items[:max_items], keywords=keywords)
        self._log(f"证据包构建完成：{len(package.items)} 条（关键词 {len(keywords)}）", "system")
        return package

    # ==================== 主张验证（事后） ====================

    def verify_claims(self, text: str, package: EvidencePackage = None) -> Dict[str, Any]:
        try:
            from harness.assurance.claim_extractor import ClaimExtractor
            from harness.assurance.sandbox import SandboxExecutor
            claims = ClaimExtractor(self.engine).extract_from_text(text or "")
        except Exception as e:
            return {"error": str(e), "total": 0, "verified": 0, "claims": []}

        sandbox = SandboxExecutor(self.engine)
        numeric = [c for c in claims if c.claim_type in ("comparative", "absolute", "threshold")]
        sandbox_results = sandbox.execute_claims(numeric) if numeric else []
        by_id = {r.get("claim_id"): r for r in sandbox_results}

        package_text = ""
        if package:
            package_text = " ".join(f"{i.title} {i.content}" for i in package.items)

        claims_data: List[Dict[str, Any]] = []
        verified = 0
        for claim in claims:
            if claim.claim_type in ("comparative", "absolute", "threshold"):
                result = by_id.get(claim.claim_id, {})
                ok = bool(result.get("success"))
                status = "verified" if ok else "failed"
            elif claim.claim_type == "source":
                key = re.sub(r"\[(arxiv|news|hf|external)\]", "", claim.original_text or "").strip()[:12]
                ok = bool(key and package_text and key in package_text)
                status = "verified" if ok else "pending_review"
            else:
                ok = False
                status = "pending_review"
            if ok:
                verified += 1
            claims_data.append({
                "claim_id": claim.claim_id,
                "text": claim.original_text,
                "claim_type": claim.claim_type,
                "status": status,
            })

        return {
            "total": len(claims),
            "verified": verified,
            "pending": len(claims) - verified,
            "claims": claims_data[:50],
            "sandbox_summary": {
                "total": len(sandbox_results),
                "passed": sum(1 for r in sandbox_results if r.get("success")),
                "pass_rate": round(
                    sum(1 for r in sandbox_results if r.get("success")) / len(sandbox_results), 3
                ) if sandbox_results else 0.0,
            },
        }

    # ==================== 算术自洽门 ====================

    def run_arithmetic_gates(self, text: str) -> List[Dict[str, Any]]:
        """
        检查报告中的数字自洽：
        - 显式等式（支持 + - × ÷ 与 万/亿 单位换算）
        - 合计句与跨行合计
        - 百分比合计（2 项及以上）
        - 占比与数值互验（700万（70%）合计 1000万）
        - 增长率推算（从 A 增长 X% 至 B）
        """
        checks: List[Dict[str, Any]] = []
        if not text:
            return checks

        # 1) 显式等式：700 + 300 = 1000、500 × 3万 = 1500万、700万 + 3000万 = 1亿
        for match in re.finditer(
                r"([^。\n]{2,90}?)\s*[=＝]\s*([0-9\.\,]+\s*(?:万|亿|千|百万)?(?:\s*[x×*÷/＋+\-－]\s*[0-9\.\,]+\s*(?:万|亿|千|百万)?)*)",
                text):
            left_raw, right_raw = match.group(1), match.group(2)
            if not re.search(r"[+－＋×x*÷/]|万|亿|千|百万", left_raw + right_raw):
                continue
            left_val = self._evaluate_arithmetic(self._clean_arithmetic_text(left_raw))
            right_val = self._evaluate_arithmetic(self._clean_arithmetic_text(right_raw))
            if left_val is None or right_val is None:
                continue
            checks.append({
                "type": "explicit_equation",
                "expression": match.group(0),
                "left_sum": round(left_val, 6),
                "right_value": round(right_val, 6),
                "passed": abs(left_val - right_val) < max(0.01, abs(right_val) * 1e-6),
                "detail": f"左侧计算 {left_val:g}，右侧 {right_val:g}",
            })

        # 2) 合计句：分项 ...，合计 X
        for match in re.finditer(
                r"([^。\n]{2,90}?)(?:合计|总计|总额|预算合计)\s*[为：:]?\s*(\d+\.?\d*)\s*(万|亿|千|百万)?",
                text):
            terms = self._collect_terms(match.group(1))
            total_val = self._number_with_unit(float(match.group(2)), match.group(3) or "")
            if len(terms) >= 2:
                left_sum = sum(self._number_with_unit(v, u) for v, u in terms)
                checks.append({
                    "type": "total_sentence",
                    "expression": match.group(0)[:90],
                    "left_sum": round(left_sum, 6),
                    "right_value": round(total_val, 6),
                    "passed": abs(left_sum - total_val) < max(0.01, abs(total_val) * 1e-6),
                    "detail": f"分项 {terms} 合计 {left_sum:g}，声明合计 {total_val:g}",
                })

        # 3) 百分比合计：A% + B% + ... = 100%（支持 2 项及以上）
        for match in re.finditer(
                r"((?:\d+\.?\d*%)(?:\s*[、,，和及＋+]\s*\d+\.?\d*%){1,})\s*[=＝]\s*(\d+\.?\d*)%?",
                text):
            vals = [float(x.rstrip("%")) for x in re.findall(r"\d+\.?\d*%", match.group(1))]
            target = float(match.group(2).rstrip("%"))
            checks.append({
                "type": "percent_sum",
                "expression": match.group(0),
                "left_sum": round(sum(vals), 6),
                "right_value": target,
                "passed": abs(sum(vals) - target) < 0.01,
                "detail": f"百分比 {vals} 合计 {sum(vals):g}%，目标 {target:g}%",
            })

        # 4) “合计 100%”附近存在百分比分项
        for match in re.finditer(r"([^。\n]{2,90}?)(?:合计|总计)\s*[为：:]?\s*100\s*%", text):
            percents = [float(x.rstrip("%")) for x in re.findall(r"(\d+\.?\d*%)", match.group(1))]
            if len(percents) >= 2:
                checks.append({
                    "type": "percent_total_sentence",
                    "expression": match.group(0)[:90],
                    "left_sum": round(sum(percents), 6),
                    "right_value": 100.0,
                    "passed": abs(sum(percents) - 100.0) < 0.01,
                    "detail": f"百分比 {percents} 合计 {sum(percents):g}%，目标 100%",
                })

        checks.extend(self._percent_allocation_checks(text))
        checks.extend(self._growth_rate_checks(text))
        checks.extend(self._block_total_checks(text))
        checks.extend(self._table_budget_checks(text))
        checks.extend(self._stage_budget_checks(text))

        return checks

    @staticmethod
    def _clean_arithmetic_text(raw: str) -> str:
        """剥离中文标签（如“A线 700万”），只保留数字、单位字与运算符。"""
        return re.sub(r"[^0-9\.\,\sx×*÷/＋+\-－万千亿百]+", "", raw)

    @staticmethod
    def _number_with_unit(value: float, unit: str = "") -> float:
        return value * {"": 1.0, "千": 1e3, "万": 1e4, "百万": 1e6, "亿": 1e8}.get(unit or "", 1.0)

    @staticmethod
    def _collect_terms(segment: str) -> List[tuple]:
        terms = []
        for match in re.finditer(r"(\d+\.?\d*)\s*(万|亿|千|百万)?(?![%％])", segment):
            value = float(match.group(1).replace(",", ""))
            unit = match.group(2) or ""
            if not unit and value >= 1000 and float(value).is_integer():
                continue
            terms.append((value, unit))
        return terms

    @staticmethod
    def _evaluate_arithmetic(expr: str) -> Optional[float]:
        """安全计算带中文单位（万/亿/千/百万）的算术表达式。"""
        normalized = expr.replace(",", "")
        for cn, factor in (("亿", 100000000), ("百万", 1000000), ("万", 10000), ("千", 1000)):
            normalized = re.sub(rf"(\d+(?:\.\d+)?)\s*{cn}", rf"\1*{factor}", normalized)
        normalized = (
            normalized.replace("×", "*").replace("x", "*").replace("X", "*")
            .replace("÷", "/").replace("＋", "+").replace("－", "-")
            .replace("（", "(").replace("）", ")").replace("%", "")
        ).strip()
        if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s]+", normalized):
            return None
        allowed = (
            ast.Expression, ast.BinOp, ast.Constant, ast.UnaryOp,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Load,
        )
        try:
            tree = ast.parse(normalized, mode="eval")
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                    return None
                if not isinstance(node, allowed):
                    return None
            return float(eval(normalized, {"__builtins__": {}}, {}))
        except Exception:
            return None

    def _percent_allocation_checks(self, text: str) -> List[Dict[str, Any]]:
        """占比互验：700万（70%）且合计 1000万，则 700万 必须等于 70%。"""
        checks: List[Dict[str, Any]] = []
        for match in re.finditer(
                r"(\d+\.?\d*)\s*(万|亿|千|百万)?\s*[（(]\s*(\d+\.?\d*)\s*%", text):
            value = self._number_with_unit(float(match.group(1)), match.group(2) or "")
            percent = float(match.group(3))
            window = text[max(0, match.start() - 140): match.end() + 140]
            total_match = re.search(
                r"(?:合计|总计|总额|总预算)\s*[为：:]?\s*(\d+\.?\d*)\s*(万|亿|千|百万)?",
                window,
            )
            if not total_match:
                continue
            total = self._number_with_unit(float(total_match.group(1)), total_match.group(2) or "")
            if total <= 0:
                continue
            expected = total * percent / 100.0
            checks.append({
                "type": "percent_allocation",
                "expression": match.group(0),
                "left_sum": round(value, 6),
                "right_value": round(expected, 6),
                "passed": abs(value - expected) < max(0.01, abs(expected) * 0.01),
                "detail": f"{value:g} 对应 {percent:g}% 的 {total:g}（应为 {expected:g}）",
            })

        # 反向模式：Y% 的 Z = X
        for match in re.finditer(
                r"(\d+\.?\d*)\s*%\s*的\s*(\d+\.?\d*)\s*(万|亿|千|百万)?\s*[=＝]\s*(\d+\.?\d*)\s*(万|亿|千|百万)?",
                text):
            total = self._number_with_unit(float(match.group(2)), match.group(3) or "")
            actual = self._number_with_unit(float(match.group(4)), match.group(5) or "")
            expected = total * float(match.group(1)) / 100.0
            checks.append({
                "type": "percent_allocation",
                "expression": match.group(0),
                "left_sum": round(actual, 6),
                "right_value": round(expected, 6),
                "passed": abs(actual - expected) < max(0.01, abs(expected) * 0.01),
                "detail": f"{match.group(1)}% 的 {total:g} 应为 {expected:g}，实际 {actual:g}",
            })
        return checks

    def _growth_rate_checks(self, text: str) -> List[Dict[str, Any]]:
        """增长率推算：从 A 增长/下降 X% 至 B。"""
        checks: List[Dict[str, Any]] = []
        patterns = [
            (
                r"从\s*(\d+\.?\d*)\s*(万|亿|千|百万)?\s*(?:上升|增长|提高|增加)\s*(\d+\.?\d*)\s*%\s*(?:至|到|达)\s*(\d+\.?\d*)\s*(万|亿|千|百万)?",
                True,
            ),
            (
                r"从\s*(\d+\.?\d*)\s*(万|亿|千|百万)?\s*(?:下降|降低|减少)\s*(\d+\.?\d*)\s*%\s*(?:至|到|达)\s*(\d+\.?\d*)\s*(万|亿|千|百万)?",
                False,
            ),
        ]
        for pattern, is_growth in patterns:
            for match in re.finditer(pattern, text):
                base = self._number_with_unit(float(match.group(1)), match.group(2) or "")
                rate = float(match.group(3))
                result = self._number_with_unit(float(match.group(4)), match.group(5) or "")
                expected = base * (1 + rate / 100.0) if is_growth else base * (1 - rate / 100.0)
                checks.append({
                    "type": "growth_rate",
                    "expression": match.group(0),
                    "left_sum": round(result, 6),
                    "right_value": round(expected, 6),
                    "passed": abs(result - expected) < max(0.01, abs(expected) * 0.01),
                    "detail": f"从 {base:g} {'增长' if is_growth else '下降'} {rate:g}% 应为 {expected:g}，实际 {result:g}",
                })
        return checks

    def _block_total_checks(self, text: str) -> List[Dict[str, Any]]:
        """跨行合计：分项与合计位于不同段落时仍可核对。"""
        checks: List[Dict[str, Any]] = []
        for match in re.finditer(
                r"(?:合计|总计|总额)\s*[为：:]?\s*(\d+\.?\d*)\s*(万|亿|千|百万)?", text or ""):
            total_val = self._number_with_unit(float(match.group(1)), match.group(2) or "")
            prefix = text[max(0, match.start() - 300): match.start()]
            # 若前缀中已存在更早的合计声明，只取最近一次合计之后的文本
            last_total = max(prefix.rfind("合计"), prefix.rfind("总计"), prefix.rfind("总额"))
            if last_total >= 0:
                prefix = prefix[last_total + 2:]
            terms = self._collect_terms(prefix)
            if len(terms) >= 2:
                left_sum = sum(self._number_with_unit(v, u) for v, u in terms)
                checks.append({
                    "type": "block_total",
                    "expression": prefix[-90:].replace("\n", " "),
                    "left_sum": round(left_sum, 6),
                    "right_value": round(total_val, 6),
                    "passed": abs(left_sum - total_val) < max(0.01, abs(total_val) * 1e-6),
                    "detail": f"跨行分项 {terms} 合计 {left_sum:g}，声明合计 {total_val:g}",
                })
        return checks

    @staticmethod
    def _parse_amount_cell(cell: str) -> Optional[float]:
        match = re.search(r"(\d+\.?\d*)\s*(亿元|万元|亿|万|元)?", cell or "")
        if not match:
            return None
        value = float(match.group(1))
        unit = match.group(2) or ""
        scale = {"": 1.0, "元": 1.0, "万": 1e4, "万元": 1e4, "亿": 1e8, "亿元": 1e8}.get(unit, 1.0)
        return value * scale

    def _table_budget_checks(self, text: str) -> List[Dict[str, Any]]:
        """
        表格列级占比校验：
        - 含“金额/预算”列的 Markdown 表格，若同时有“占比/比例”列，
          逐行核验 金额/合计 与声明占比是否一致（容差 1 个百分点）。
        - 若表格有“合计/总计”行，同时核验分项金额求和。
        """
        checks: List[Dict[str, Any]] = []
        lines = (text or "").splitlines()
        i = 0
        while i < len(lines):
            header_line = lines[i].strip()
            if not header_line.startswith("|") or not re.search(r"金额|预算|费用|投入", header_line):
                i += 1
                continue
            if i + 1 >= len(lines) or not re.fullmatch(r"\|[\s:\-|]+\|?", lines[i + 1].strip()):
                i += 1
                continue
            headers = [c.strip() for c in header_line.strip("|").split("|")]
            rows = []
            k = i + 2
            while k < len(lines) and lines[k].strip().startswith("|"):
                cells = [c.strip() for c in lines[k].strip().strip("|").split("|")]
                if len(cells) >= len(headers):
                    rows.append(cells)
                k += 1

            amount_col = next(
                (idx for idx, h in enumerate(headers) if re.search(r"金额|预算|费用|投入", h)),
                None,
            )
            pct_col = next(
                (idx for idx, h in enumerate(headers) if re.search(r"占比|比例", h)),
                None,
            )
            if amount_col is None:
                i = k
                continue

            total_row = next(
                (row for row in rows if any(re.search(r"合计|总计", c) for c in row)),
                None,
            )
            data_rows = [row for row in rows if row is not total_row]
            amounts = []
            for row in data_rows:
                if amount_col < len(row):
                    value = self._parse_amount_cell(row[amount_col])
                    if value is not None:
                        amounts.append((row, value))

            total_value = None
            if total_row is not None and amount_col < len(total_row):
                total_value = self._parse_amount_cell(total_row[amount_col])

            if total_value is not None and len(amounts) >= 2:
                left_sum = sum(v for _row, v in amounts)
                checks.append({
                    "type": "budget_total",
                    "expression": total_row[0][:30] if total_row else "合计行",
                    "left_sum": round(left_sum, 6),
                    "right_value": round(total_value, 6),
                    "passed": abs(left_sum - total_value) < max(1.0, abs(total_value) * 1e-6),
                    "detail": f"预算分项合计 {left_sum:g}，合计行 {total_value:g}",
                })

            if pct_col is not None and total_value and total_value > 0:
                for row, amount in amounts:
                    if pct_col >= len(row):
                        continue
                    pct_match = re.search(r"(\d+\.?\d*)\s*%", row[pct_col])
                    if not pct_match:
                        continue
                    declared = float(pct_match.group(1))
                    actual = amount / total_value * 100.0
                    checks.append({
                        "type": "budget_ratio",
                        "expression": f"{row[0][:24]} | {row[pct_col]}",
                        "left_sum": round(actual, 2),
                        "right_value": declared,
                        "passed": abs(actual - declared) < 1.0,
                        "detail": f"{row[0][:24]} 实际占比 {actual:.1f}%，声明 {declared:.0f}%",
                    })
            i = k
        return checks

    def _stage_budget_checks(self, text: str) -> List[Dict[str, Any]]:
        """
        分阶段预算校验：
        - 识别“第1-3个月 / 前6个月 / 第X阶段”等阶段金额
        - 若阶段金额 ≥2 项，加总后与“总预算/总额/合计”比对
        - 也解析“阶段/月份 + 金额”型 Markdown 表格
        """
        checks: List[Dict[str, Any]] = []
        stage_amounts: List[tuple] = []

        # 句子模式：前/后 N 个月、第 N-M 个月、第 N 阶段 + 金额
        patterns = [
            r"(?:前|后)\s*(\d+)\s*个?月[^。\n]{0,40}?(\d+\.?\d*)\s*(亿元|万元|亿|万|元)",
            r"第\s*(\d+)\s*[-–至到]\s*(\d+)\s*个?月[^。\n]{0,40}?(\d+\.?\d*)\s*(亿元|万元|亿|万|元)",
            r"第\s*(\d+)\s*阶段[^。\n]{0,40}?(\d+\.?\d*)\s*(亿元|万元|亿|万|元)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text or ""):
                label = match.group(0)[:30]
                groups = [g for g in match.groups() if g is not None]
                amount_text = groups[-2]
                unit = groups[-1]
                value = float(amount_text) * {"": 1.0, "元": 1.0, "万": 1e4, "万元": 1e4, "亿": 1e8, "亿元": 1e8}.get(unit, 1.0)
                stage_amounts.append((label, value))

        # 表格模式：阶段/月份 + 金额
        lines = (text or "").splitlines()
        i = 0
        while i < len(lines):
            header_line = lines[i].strip()
            if not header_line.startswith("|") or not re.search(r"阶段|月份|周期|时间", header_line):
                i += 1
                continue
            if i + 1 >= len(lines) or not re.fullmatch(r"\|[\s:\-|]+\|?", lines[i + 1].strip()):
                i += 1
                continue
            headers = [c.strip() for c in header_line.strip("|").split("|")]
            amount_col = next(
                (idx for idx, h in enumerate(headers) if re.search(r"金额|预算|投入|费用", h)),
                None,
            )
            if amount_col is None:
                i += 1
                continue
            k = i + 2
            while k < len(lines) and lines[k].strip().startswith("|"):
                cells = [c.strip() for c in lines[k].strip().strip("|").split("|")]
                if len(cells) >= len(headers) and amount_col < len(cells):
                    value = self._parse_amount_cell(cells[amount_col])
                    if value is not None:
                        stage_amounts.append((cells[0][:30], value))
                k += 1
            i = k

        if len(stage_amounts) < 2:
            return checks

        # 在文本中找总预算/总额/合计
        total_value = None
        total_text = ""
        for match in re.finditer(r"(?:总预算|预算总额|总额|合计)\s*[为：:]?\s*(\d+\.?\d*)\s*(亿元|万元|亿|万|元)", text or ""):
            value = float(match.group(1)) * {"": 1.0, "元": 1.0, "万": 1e4, "万元": 1e4, "亿": 1e8, "亿元": 1e8}.get(match.group(2) or "", 1.0)
            total_value = value
            total_text = match.group(0)[:30]
            break
        if total_value is None:
            return checks

        stage_sum = sum(v for _label, v in stage_amounts)
        checks.append({
            "type": "stage_budget_total",
            "expression": total_text,
            "left_sum": round(stage_sum, 6),
            "right_value": round(total_value, 6),
            "passed": abs(stage_sum - total_value) < max(1.0, abs(total_value) * 1e-6),
            "detail": f"分阶段预算合计 {stage_sum:g}，总预算 {total_value:g}（共 {len(stage_amounts)} 个阶段）",
        })
        return checks

    # ==================== 假设分级 ====================

    def _classify_assumption(self, sentence: str) -> Optional[str]:
        if any(marker in sentence for marker in self.A_MARKERS):
            return "A"
        if any(marker in sentence for marker in self.B_MARKERS):
            return "B"
        if any(marker in sentence for marker in self.C_MARKERS):
            return "C"
        return None

    def grade_assumptions(self, text: str) -> List[Dict[str, Any]]:
        """
        提取并分级假设：
        A 强假设（有来源/数据）；B 经验估计；C 弱假设（待验证）。
        """
        assumptions: List[Dict[str, Any]] = []
        sentences = re.split(r"[。！？\n；;]+", text or "")
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            grade = self._classify_assumption(sentence)
            if not grade:
                continue
            marker = next(
                (m for m in self.A_MARKERS + self.B_MARKERS + self.C_MARKERS if m in sentence),
                "",
            )
            assumptions.append({
                "sentence": sentence[:160],
                "grade": grade,
                "matched_keyword": marker,
            })
        return assumptions

    # ==================== 证据报告 ====================

    def build_report(self, text: str, question: str = "",
                     package: EvidencePackage = None) -> Dict[str, Any]:
        verification = self.verify_claims(text, package)
        arithmetic = self.run_arithmetic_gates(text)
        assumptions = self.grade_assumptions(text)
        arith_passed = sum(1 for check in arithmetic if check.get("passed"))
        evidence_refs = len(re.findall(r"\[E\d{3}\]", text or ""))

        confidence = 0.5
        if verification.get("total"):
            confidence = 0.4 + 0.4 * verification["verified"] / verification["total"]
        if arithmetic:
            confidence += 0.1 * (arith_passed / len(arithmetic)) - 0.05
        confidence = round(max(0.1, min(1.0, confidence)), 3)

        return {
            "question": question[:200],
            "evidence_package": package.summarize() if package else {},
            "claim_verification": verification,
            "arithmetic_gates": {
                "checks": arithmetic,
                "passed": arith_passed,
                "total": len(arithmetic),
                "requires_retry": any(not c.get("passed", True) for c in arithmetic),
            },
            "assumption_grading": assumptions,
            "evidence_references": evidence_refs,
            "confidence_score": confidence,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
