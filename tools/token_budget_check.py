#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Token 预算基线检查：对比一次真实辩论的 token 汇总，防止 token 悄悄涨回去。

用法：
    python tools/token_budget_check.py --file 新版P3_token.json
    python tools/token_budget_check.py --update-baseline \
        --file 新版P3_token.json --label 新版P3 --revision 9a87aab

输入可以是 run_debate_token_compare.py 的汇总 JSON，也可以是原始 CALL_LOG 列表。
基线默认存到 docs/token_budget_baseline.json。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = ROOT / "docs" / "token_budget_baseline.json"


def _load_token_data(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "totals" in data:
        return data["totals"], data.get("by_caller", {})
    if isinstance(data, list):
        totals = {
            "calls": len(data),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        by_caller: Dict[str, Dict[str, Any]] = {}
        for entry in data:
            caller = str(entry.get("caller") or "unknown")
            prompt = int(entry.get("prompt_tokens", 0) or 0)
            completion = int(entry.get("completion_tokens", 0) or 0)
            totals["prompt_tokens"] += prompt
            totals["completion_tokens"] += completion
            totals["total_tokens"] += prompt + completion
            item = by_caller.setdefault(
                caller, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            )
            item["calls"] += 1
            item["prompt_tokens"] += prompt
            item["completion_tokens"] += completion
            item["total_tokens"] += prompt + completion
        return totals, by_caller
    raise ValueError("无法识别的 token 文件格式：需要汇总 JSON 或 CALL_LOG 列表")


def _print_result(result: Dict[str, Any]) -> None:
    print(
        json.dumps(result, ensure_ascii=False, indent=2),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Token 预算基线检查")
    parser.add_argument("--file", type=Path, required=True, help="本次运行的 token 汇总或 CALL_LOG JSON")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="基线文件路径")
    parser.add_argument("--old-total", type=int, default=407479, help="旧版基线总 token（默认 6f2665c 实测）")
    parser.add_argument("--target-savings", type=float, default=0.30, help="目标总降幅（默认 30%）")
    parser.add_argument("--label", default="", help="更新基线时的运行标签")
    parser.add_argument("--revision", default="", help="更新基线时的代码版本")
    parser.add_argument("--update-baseline", action="store_true", help="用本次数据重建基线")
    args = parser.parse_args()

    totals, by_caller = _load_token_data(args.file)
    budget_total = round(args.old_total * (1 - args.target_savings))

    if args.update_baseline:
        baseline = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "label": args.label or Path(args.file).stem,
            "revision": args.revision,
            "old_total": args.old_total,
            "target_savings": args.target_savings,
            "budget_total": budget_total,
            "totals": totals,
            "by_caller": by_caller,
        }
        args.baseline.write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _print_result(
            {
                "status": "BASELINE_UPDATED",
                "baseline": str(args.baseline),
                "totals": totals,
                "budget_total": budget_total,
            }
        )
        return 0

    if not args.baseline.exists():
        print(
            json.dumps(
                {"status": "NO_BASELINE", "baseline": str(args.baseline)},
                ensure_ascii=False,
            )
        )
        return 1

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_total = int(baseline["totals"]["total_tokens"])
    current_total = int(totals["total_tokens"])
    baseline_budget = int(baseline.get("budget_total") or budget_total)
    over_budget = current_total > baseline_budget
    over_baseline = current_total > baseline_total

    _print_result(
        {
            "status": "FAIL" if over_budget else "PASS",
            "current_total": current_total,
            "baseline_total": baseline_total,
            "budget_total": baseline_budget,
            "delta_vs_baseline": current_total - baseline_total,
            "delta_vs_old": current_total - int(baseline["old_total"]),
            "savings_vs_old": round(
                (1 - current_total / int(baseline["old_total"])) * 100, 1
            ),
            "over_budget": over_budget,
            "over_baseline": over_baseline,
            "totals": totals,
        }
    )
    return 1 if over_budget else 0


if __name__ == "__main__":
    sys.exit(main())
