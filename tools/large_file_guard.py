#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大文件看门狗：防止核心应用持续膨胀出新的巨型文件。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "docs" / "large_file_baseline.json"
DEFAULT_THRESHOLD = 2500
ALLOWED_GROWTH = 100
CORE_DIRS = [
    "access",
    "addons",
    "auth",
    "core",
    "data",
    "evolution",
    "external",
    "governance",
    "harness",
    "webhook",
]


def scan_lines(threshold: int) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for dir_name in CORE_DIRS:
        for path in (ROOT / dir_name).rglob("*.py"):
            try:
                lines = len(path.read_text(encoding="utf-8").splitlines())
            except Exception:
                continue
            if lines >= threshold:
                key = str(path.relative_to(ROOT)).replace("\\", "/")
                result[key] = lines
    return result


def load_baseline() -> Dict[str, int]:
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        return {key: int(value) for key, value in data.items()}
    except Exception:
        return {}


def check(current: Dict[str, int]) -> List[str]:
    baseline = load_baseline()
    failures: List[str] = []
    for path, lines in sorted(current.items()):
        if path not in baseline:
            failures.append(f"新增大文件: {path} ({lines} 行)")
        else:
            growth = lines - baseline[path]
            if growth > ALLOWED_GROWTH:
                failures.append(
                    f"大文件膨胀: {path} {baseline[path]} -> {lines} (+{growth})"
                )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="大文件看门狗")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--check", action="store_true", help="检查当前大文件是否突破基线")
    args = parser.parse_args()

    current = scan_lines(args.threshold)
    if args.update_baseline:
        BASELINE_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print("LARGE_FILE_GUARD: BASELINE_UPDATED")
        for path, lines in sorted(current.items()):
            print(f"  {path}: {lines}")
        return 0

    failures = check(current)
    print(f"LARGE_FILE_GUARD: threshold={args.threshold}")
    for path, lines in sorted(current.items()):
        print(f"  {path}: {lines}")
    if failures:
        print("LARGE_FILE_GUARD: FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("LARGE_FILE_GUARD: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
