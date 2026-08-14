#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽取式摘要保留率探针：检查链接/日期/关键数字在压缩前后的保留情况。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from external.ai_client import AIClient
from harness.processors.debate import DebateEngine


DEFAULT_QUESTIONS = [
    "如何设计一个多变量优化框架并评估综合策略，同时平衡长期目标与短期资源约束？",
    "2026年中国储能产业政策对工商业储能投资回报率有什么影响？",
    "GLP-1受体激动剂对心血管疾病预防的长期获益与风险有哪些证据？",
    "AI智能体在企业软件自动化中的落地案例和成本效益如何？",
    "如何设计一门提升中学生批判性思维的课程并评估其教学效果？",
]

LINK_RE = re.compile(r"https?://")
DATE_RE = re.compile(r"(202[0-9]年|202[0-9]-\d{1,2}-\d{1,2}|\d{1,2}月\d{1,2}日)")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|元|万|亿|天|小时|分钟|年|月|日|倍|美元)")


def _counts(text: str) -> Dict[str, int]:
    return {
        "links": len(LINK_RE.findall(text)),
        "dates": len(DATE_RE.findall(text)),
        "numbers": len(NUMBER_RE.findall(text)),
    }


def _rate(after: int, before: int) -> float:
    return round(after / max(1, before) * 100, 1)


def run_one(question: str) -> Dict[str, Any]:
    logs = []
    debate = DebateEngine.__new__(DebateEngine)
    debate.ai = AIClient()
    debate.log = lambda message, level="system": logs.append((str(message), level))
    started = time.time()
    result = debate._fetch_external_overview(question)
    elapsed = round(time.time() - started, 2)
    raw = getattr(debate, "_last_qianfan_raw", "") or ""
    items = getattr(debate, "_last_qianfan_items", 0)
    raw_counts = _counts(raw)
    out_counts = _counts(result)
    return {
        "question": question,
        "raw_items": items,
        "raw_chars": len(raw),
        "out_chars": len(result),
        "links_raw": raw_counts["links"],
        "links_out": out_counts["links"],
        "dates_raw": raw_counts["dates"],
        "dates_out": out_counts["dates"],
        "numbers_raw": raw_counts["numbers"],
        "numbers_out": out_counts["numbers"],
        "links_keep_rate": _rate(out_counts["links"], raw_counts["links"]),
        "dates_keep_rate": _rate(out_counts["dates"], raw_counts["dates"]),
        "numbers_keep_rate": _rate(out_counts["numbers"], raw_counts["numbers"]),
        "elapsed": elapsed,
        "head": result[:80],
    }


def to_markdown(rows: List[Dict[str, Any]], generated_at: str) -> str:
    lines = [
        "# 千帆抽取式摘要保留率探针",
        "",
        f"- 生成日期：{generated_at}",
        "- 模式：QIANFAN_OVERVIEW_MODE=extractive，jieba TextRank 抽取式摘要",
        "- 说明：保留率 = 压缩后数量 / 原始数量，仅作趋势参考",
        "",
        "| 问题 | 原始条数 | 原始字数 | 摘要字数 | 链接 原→压 | 日期 原→压 | 数字 原→压 | 链接保留率 | 日期保留率 | 数字保留率 | 耗时(秒) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['question'][:28]} | {row['raw_items']} | {row['raw_chars']} | "
            f"{row['out_chars']} | {row['links_raw']}→{row['links_out']} | "
            f"{row['dates_raw']}→{row['dates_out']} | {row['numbers_raw']}→{row['numbers_out']} | "
            f"{row['links_keep_rate']}% | {row['dates_keep_rate']}% | "
            f"{row['numbers_keep_rate']}% | {row['elapsed']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="千帆抽取式摘要保留率探针")
    parser.add_argument(
        "--questions",
        default=json.dumps(DEFAULT_QUESTIONS, ensure_ascii=False),
        help="JSON 数组格式的问题列表",
    )
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()

    questions = json.loads(args.questions)
    rows = [run_one(q) for q in questions]
    generated_at = date.today().strftime("%Y%m%d")
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"qianfan_extractive_probe_{generated_at}.md"
    json_path = out_dir / f"qianfan_extractive_probe_{generated_at}.json"
    md_path.write_text(to_markdown(rows, generated_at), encoding="utf-8")
    json_path.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(), "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"rows": len(rows), "md": str(md_path), "json": str(json_path)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
