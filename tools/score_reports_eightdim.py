#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对指定报告文件（Markdown / Word）执行系统八维评分并输出汇总。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.scoring import score_report, score_summary


DEFAULT_OUT_DIR = ROOT / "docs" / "输出" / "评分"


DIMENSION_LABELS = [
    ("argument_depth", "论证深度"),
    ("evidence_quality", "证据质量"),
    ("logic_rigor", "逻辑严谨"),
    ("perspective_diversity", "视角多样"),
    ("innovation_insight", "创新洞察"),
    ("structure_organization", "结构组织"),
    ("readability", "可读性"),
    ("practical_value", "实用价值"),
]


def read_report(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        from docx import Document

        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    return path.read_text(encoding="utf-8")


def to_markdown(rows: list, tag: str) -> str:
    lines = [
        f"# {tag}",
        "",
        "- 评分系统：core/scoring.py 本地八维启发式评分（零依赖）",
        "- 说明：仅作内部趋势参考；压缩版字数更少，启发式指标会相应偏保守",
        "",
        "| 报告 | 论证深度 | 证据质量 | 逻辑严谨 | 视角多样 | 创新洞察 | 结构组织 | 可读性 | 实用价值 | 加权总分 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        s = row["scores"]
        lines.append(
            f"| {row['file']} | {s['argument_depth']} | {s['evidence_quality']} | "
            f"{s['logic_rigor']} | {s['perspective_diversity']} | {s['innovation_insight']} | "
            f"{s['structure_organization']} | {s['readability']} | {s['practical_value']} | "
            f"{row['total']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="系统八维评分汇总")
    parser.add_argument("--file", type=Path, action="append", required=True, help="报告文件（可多次）")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="输出目录")
    parser.add_argument("--tag", default="报告八维评分", help="输出文件标签")
    args = parser.parse_args()

    rows = []
    for path in args.file:
        text = read_report(path)
        scores = score_report(text)
        rows.append(
            {
                "file": path.name,
                "chars": len(text),
                "scores": scores,
                "total": score_summary(scores),
            }
        )
    rows.sort(key=lambda r: r["total"], reverse=True)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    md_path = out_dir / f"{args.tag}_{stamp}.md"
    json_path = out_dir / f"{args.tag}_{stamp}.json"
    md_path.write_text(to_markdown(rows, args.tag), encoding="utf-8")
    json_path.write_text(
        json.dumps({"generated_at": stamp, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"reports": len(rows), "md": str(md_path), "json": str(json_path)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
