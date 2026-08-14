#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""圈复杂度与可维护性指数度量，接入回归闭环。

用法：
    python tools/complexity_metrics.py                  # 计算并写最新快照
    python tools/complexity_metrics.py --check          # 对比基线：CC 不增、MI 不降
    python tools/complexity_metrics.py --update-baseline  # 用当前值重建基线
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
NON_CORE_DIRS = {"晶体树文件夹", "tests", "tools", "dist_public"}
BASELINE_PATH = ROOT / "docs" / "complexity_baseline.json"
LATEST_PATH = ROOT / "docs" / "complexity_metrics.json"
LARGE_FILE_BASELINE_PATH = ROOT / "docs" / "large_file_baseline.json"

try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit

    RADON_AVAILABLE = True
except ImportError:
    cc_visit = None
    mi_visit = None
    RADON_AVAILABLE = False


def iter_core_py_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "application" in path.parts:
            continue
        if path.name in ("code_metrics.py", "complexity_metrics.py"):
            continue
        rel = path.relative_to(root)
        if rel.parts[0] in NON_CORE_DIRS:
            continue
        yield path


def analyze_file(path: Path) -> Dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.count("\n") + 1
    if not RADON_AVAILABLE:
        return {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "lines": lines,
            "functions": 0,
            "total_cc": 0,
            "max_cc": 0,
            "worst": "",
            "mi": 0.0,
        }
    blocks = cc_visit(source)
    total_cc = sum(b.complexity for b in blocks)
    max_block = max(blocks, key=lambda b: b.complexity, default=None)
    mi = mi_visit(source, multi=False)
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "lines": lines,
        "functions": len(blocks),
        "total_cc": total_cc,
        "max_cc": max_block.complexity if max_block else 0,
        "worst": f"{max_block.name}@{max_block.lineno}" if max_block else "",
        "mi": round(mi, 1),
    }


def collect() -> Dict[str, Any]:
    files = [analyze_file(p) for p in iter_core_py_files(ROOT)]
    try:
        large_files = set(json.loads(LARGE_FILE_BASELINE_PATH.read_text(encoding="utf-8")))
    except Exception:
        large_files = set()
    small_files = [f for f in files if f["path"] not in large_files]
    total_cc = sum(f["total_cc"] for f in files)
    total_functions = sum(f["functions"] for f in files)
    total_lines = sum(f["lines"] for f in files)
    small_lines = sum(f["lines"] for f in small_files)
    avg_cc = round(total_cc / max(1, total_functions), 2)
    avg_mi_weighted = round(
        sum(f["mi"] * f["lines"] for f in files) / max(1, total_lines),
        2,
    )
    avg_mi_weighted_small_files = round(
        sum(f["mi"] * f["lines"] for f in small_files) / max(1, small_lines),
        2,
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": len(files),
        "total_cc": total_cc,
        "total_functions": total_functions,
        "avg_cc": avg_cc,
        "max_cc": max((f["max_cc"] for f in files), default=0),
        "avg_mi_weighted": avg_mi_weighted,
        "avg_mi_weighted_small_files": avg_mi_weighted_small_files,
        "by_file": files,
    }


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def print_trends(current: Dict[str, Any], baseline: Dict[str, Any]) -> None:
    base_map = {f["path"]: f for f in baseline["by_file"]}
    cur_map = {f["path"]: f for f in current["by_file"]}
    cc_worse = []
    mi_worse = []
    for path, f in cur_map.items():
        base = base_map.get(path)
        if not base:
            continue
        if f["total_cc"] > base["total_cc"]:
            cc_worse.append((path, base["total_cc"], f["total_cc"]))
        if f["mi"] < base["mi"]:
            mi_worse.append((path, base["mi"], f["mi"]))
    cc_worse.sort(key=lambda x: x[2] - x[1], reverse=True)
    mi_worse.sort(key=lambda x: x[1] - x[2], reverse=True)
    if cc_worse:
        print("  CC 上升 Top5:")
        for path, old, new in cc_worse[:5]:
            print(f"    {path}: {old} -> {new}")
    if mi_worse:
        print("  MI 下降 Top5:")
        for path, old, new in mi_worse[:5]:
            print(f"    {path}: {old} -> {new}")
    if not cc_worse and not mi_worse:
        print("  无文件级指标恶化")


def main() -> int:
    parser = argparse.ArgumentParser(description="圈复杂度与可维护性指数度量")
    parser.add_argument("--check", action="store_true", help="对比基线并作为门禁")
    parser.add_argument("--update-baseline", action="store_true", help="重建基线")
    args = parser.parse_args()

    if not RADON_AVAILABLE:
        print("COMPLEXITY: RADON_UNAVAILABLE (跳过)")
        return 0

    current = collect()
    write_json(LATEST_PATH, current)

    if args.update_baseline:
        write_json(BASELINE_PATH, current)
        print("COMPLEXITY: BASELINE_UPDATED")
        return 0

    if not args.check:
        print(
            json.dumps(
                {
                    "total_cc": current["total_cc"],
                    "avg_cc": current["avg_cc"],
                    "max_cc": current["max_cc"],
                    "avg_mi_weighted": current["avg_mi_weighted"],
                    "avg_mi_weighted_small_files": current["avg_mi_weighted_small_files"],
                    "latest": str(LATEST_PATH),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if not BASELINE_PATH.exists():
        write_json(BASELINE_PATH, current)
        print("COMPLEXITY: BASELINE_CREATED")
        print(
            json.dumps(
                {
                    "total_cc": current["total_cc"],
                    "avg_mi_weighted": current["avg_mi_weighted"],
                    "avg_mi_weighted_small_files": current["avg_mi_weighted_small_files"],
                },
                ensure_ascii=False,
            )
        )
        return 0

    baseline = load_json(BASELINE_PATH)
    cc_delta = current["total_cc"] - baseline["total_cc"]
    mi_delta = current["avg_mi_weighted"] - baseline["avg_mi_weighted"]
    ok = cc_delta <= 0 and mi_delta >= 0
    print(f"  total_cc: {baseline['total_cc']} -> {current['total_cc']} ({cc_delta:+d})")
    print(
        f"  avg_mi_weighted: {baseline['avg_mi_weighted']} -> "
        f"{current['avg_mi_weighted']} ({mi_delta:+.2f})"
    )
    print(
        f"  avg_mi_weighted_small_files: {current['avg_mi_weighted_small_files']}"
    )
    print_trends(current, baseline)
    print("COMPLEXITY: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
