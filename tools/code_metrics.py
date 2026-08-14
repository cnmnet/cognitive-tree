#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码基线度量：行数口径、单体文件、残留目录、敏感文件跟踪检查。"""

from __future__ import annotations

import json
import re
import argparse
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_SCOPE_DIRS = {"晶体树文件夹"}
NON_CORE_DIRS = {"晶体树文件夹", "tests", "tools"}
SENSITIVE_PATTERNS = [
    re.compile(r"(^|/)(\.env|security\.key|chat_sessions\.db|users\.json|user_profile\.json|crystals\.bak)$"),
    re.compile(r"(^|/)(晶体数据|晶体数据 - 副本|系统日志|model_cache|__pycache__|\.pytest_cache)(/|$)"),
    re.compile(r"\.zip$"),
]


def iter_py_files(root: Path, include_application: bool = False):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if "application" in path.parts and not include_application:
            continue
        if path.name == "code_metrics.py":
            continue
        yield path


def count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
    except OSError:
        return 0


def relative_top(path: Path) -> str:
    rel = path.relative_to(ROOT)
    return rel.parts[0] if len(rel.parts) > 1 else "(root)"


def collect_metrics(include_application: bool = False) -> dict:
    files = list(iter_py_files(ROOT, include_application))
    stats = []
    for path in files:
        stats.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "top": relative_top(path),
                "lines": count_lines(path),
            }
        )

    total_lines = sum(item["lines"] for item in stats)
    core_lines = sum(
        item["lines"] for item in stats if item["top"] not in NON_CORE_DIRS
    )
    data_lines = sum(
        item["lines"] for item in stats if item["top"] in DATA_SCOPE_DIRS
    )

    by_top = defaultdict(lambda: {"files": 0, "lines": 0})
    for item in stats:
        by_top[item["top"]]["files"] += 1
        by_top[item["top"]]["lines"] += item["lines"]

    top_files = sorted(stats, key=lambda item: item["lines"], reverse=True)[:20]

    stale_dirs = []
    for child in sorted(ROOT.iterdir()):
        if not child.is_dir():
            continue
        non_pyc = [
            p
            for p in child.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
        if not non_pyc:
            stale_dirs.append(str(child.relative_to(ROOT)).replace("\\", "/"))

    tracked_sensitive = []
    git = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if git.returncode == 0:
        for name in git.stdout.split("\0"):
            if name and any(pattern.search(name) for pattern in SENSITIVE_PATTERNS):
                tracked_sensitive.append(name)

    return {
        "generated_at": date.today().isoformat(),
        "root": str(ROOT),
        "total_py_files": len(stats),
        "total_py_lines": total_lines,
        "core_application_lines": core_lines,
        "data_scope_lines": data_lines,
        "by_top_level": {
            top: {"files": value["files"], "lines": value["lines"]}
            for top, value in sorted(by_top.items(), key=lambda kv: -kv[1]["lines"])
        },
        "largest_files": [
            {"path": item["path"], "lines": item["lines"]} for item in top_files
        ],
        "stale_dirs": stale_dirs,
        "tracked_sensitive": tracked_sensitive,
    }


def to_markdown(metrics: dict) -> str:
    lines = [
        "# 代码基线度量",
        "",
        f"- 生成日期：{metrics['generated_at']}",
        f"- 工作区：`{metrics['root']}`",
        f"- 全项目 .py 行数：{metrics['total_py_lines']}",
        f"- 核心应用代码行数（不含 tests/tools/数据目录）：{metrics['core_application_lines']}",
        "",
        "## 分目录",
        "",
        "| 目录 | 文件数 | 行数 |",
        "| --- | ---: | ---: |",
    ]
    for top, value in metrics["by_top_level"].items():
        lines.append(f"| {top} | {value['files']} | {value['lines']} |")
    lines.extend(["", "## 最大单体文件", "", "| 文件 | 行数 |", "| --- | ---: |"])
    for item in metrics["largest_files"]:
        lines.append(f"| {item['path']} | {item['lines']} |")
    lines.extend(
        [
            "",
            "## 残留目录与敏感文件",
            "",
            f"- 仅含编译产物的残留目录：{', '.join(metrics['stale_dirs']) or '无'}",
            f"- 被 git 跟踪的敏感文件：{', '.join(metrics['tracked_sensitive']) or '无'}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="代码基线度量")
    parser.add_argument(
        "--include-application",
        action="store_true",
        help="把已停用的 application/ 也纳入统计",
    )
    args = parser.parse_args()
    metrics = collect_metrics(args.include_application)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    report_path = ROOT / "docs" / f"baseline_metrics_{metrics['generated_at'].replace('-', '')}.md"
    report_path.write_text(to_markdown(metrics), encoding="utf-8")
    print(f"\nREPORT={report_path}")
    return 0 if not metrics["tracked_sensitive"] else 1


if __name__ == "__main__":
    sys.exit(main())
