#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度千帆数据质量/数量探针。

用法：
    python tools/qianfan_probe.py

未配置 Key 时输出 SKIPPED；配置后输出每个查询的数量与质量指标，
并写入 docs/qianfan_probe_YYYYMMDD.md / .json。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from external.providers.baidu_qianfan import BaiduQianfanProvider


SAMPLE_QUERIES = [
    "大模型 智能体 Agent 最新进展",
    "认知科学 决策机制 研究",
    "AI 辅助编程 研发效率 案例",
    "知识管理 深度消化 方法",
]


def probe() -> Dict[str, Any]:
    provider = BaiduQianfanProvider()
    if not provider.is_available():
        return {
            "status": "SKIPPED",
            "reason": "未配置 BAIDU_API_KEY 或 BAIDU_APPBUILDER_API_KEY",
            "rows": [],
        }

    rows: List[Dict[str, Any]] = []
    for query in SAMPLE_QUERIES:
        started = time.time()
        try:
            results = provider.search(query, top_k=5)
            latency = round(time.time() - started, 2)
        except Exception as exc:
            rows.append({"query": query, "error": str(exc), "count": 0, "latency": None})
            continue
        titles = [r.title for r in results if r.title]
        contents = [r.content for r in results if r.content]
        rows.append(
            {
                "query": query,
                "count": len(results),
                "unique_titles": len(set(titles)),
                "avg_title_len": round(sum(map(len, titles)) / max(1, len(titles)), 1),
                "avg_content_len": round(
                    sum(map(len, contents)) / max(1, len(contents)), 1
                ),
                "with_url": sum(1 for r in results if r.url),
                "sources": sorted({r.source for r in results if r.source}),
                "latency": latency,
                "sample": (titles[0][:80] if titles else ""),
            }
        )
    return {"status": "DONE", "rows": rows}


def to_markdown(data: Dict[str, Any], generated_at: str) -> str:
    lines = [
        "# 百度千帆数据质量探针",
        "",
        f"- 生成日期：{generated_at}",
        f"- 状态：{data['status']}",
    ]
    if data.get("reason"):
        lines.append(f"- 原因：{data['reason']}")
        lines.append("")
        return "\n".join(lines)
    lines += [
        "",
        "| 查询 | 数量 | 去重标题 | 平均标题长度 | 平均摘要长度 | 带链接 | 来源 | 耗时(秒) | 样例 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in data["rows"]:
        lines.append(
            f"| {row['query']} | {row['count']} | {row['unique_titles']} | "
            f"{row['avg_title_len']} | {row['avg_content_len']} | {row['with_url']} | "
            f"{', '.join(row['sources']) or '-'} | {row['latency']} | {row['sample']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    generated_at = date.today().isoformat()
    data = probe()
    if data["status"] == "SKIPPED":
        print(json.dumps({"status": data["status"], "reason": data["reason"]}, ensure_ascii=False))
        return 0
    report_md = ROOT / "docs" / f"qianfan_probe_{generated_at.replace('-', '')}.md"
    report_json = report_md.with_suffix(".json")
    report_md.write_text(to_markdown(data, generated_at), encoding="utf-8")
    report_json.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(), **data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"status": data["status"], "report": str(report_md)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
