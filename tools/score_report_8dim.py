#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地八维评分脚本（workbuddy 风格，启发式，仅作内部趋势参考）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.scoring import score_report, score_summary


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tools/score_report_8dim.py <report.md>")
        return 1
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    scores = score_report(text)
    print(
        json.dumps(
            {"file": str(path), "scores": scores, "weighted_total": score_summary(scores)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
