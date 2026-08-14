#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基线跑分：对报告目录下的报告执行本地八维评分，输出汇总。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.scoring import score_report


DEFAULT_OUT_DIR = ROOT / "docs" / "输出" / "评分"


def collect_reports(reports_dir: Path, explicit: List[Path]) -> List[Path]:
    if explicit:
        return explicit
    if not reports_dir.exists():
        return []
    return sorted(reports_dir.glob("*.md"))


def to_markdown(rows: list, generated_at: str) -> str:
    lines = [
        "# 基线八维评分",
        "",
        f"- 生成日期：{generated_at}",
        "- 说明：workbuddy 风格本地启发式评分，仅作内部趋势参考。",
        "",
        "| 文件 | 论证深度 | 证据质量 | 逻辑严谨 | 视角多样 | 创新洞察 | 结构组织 | 可读性 | 实用价值 | 加权总分 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        s = row["scores"]
        lines.append(
            f"| {row['file']} | {s['argument_depth']} | {s['evidence_quality']} | "
            f"{s['logic_rigor']} | {s['perspective_diversity']} | "
            f"{s['innovation_insight']} | {s['structure_organization']} | "
            f"{s['readability']} | {s['practical_value']} | {row['total']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="基线八维评分")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "docs" / "baseline_reports")
    parser.add_argument("--file", type=Path, action="append", default=[])
    args = parser.parse_args()

    reports = collect_reports(args.reports_dir, args.file)
    if not reports:
        print("BASELINE_SCORING: NO_REPORTS")
        return 0

    rows = []
    for path in reports:
        scores = score_report(path.read_text(encoding="utf-8"))
        total = round(sum(scores.values()) / len(scores), 1)
        rows.append({"file": path.name, "scores": scores, "total": total})

    generated_at = date.today().isoformat()
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_md = DEFAULT_OUT_DIR / f"baseline_scoring_{generated_at.replace('-', '')}.md"
    report_json = report_md.with_suffix(".json")
    report_md.write_text(to_markdown(rows, generated_at), encoding="utf-8")
    report_json.write_text(
        json.dumps({"generated_at": generated_at, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"reports": len(rows), "report_md": str(report_md)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
