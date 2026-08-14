#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核心代码小方法扫描：找出可评估合并的私有小方法。"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Tuple


ROOT = Path(__file__).resolve().parent.parent
CORE_DIRS = [
    "access",
    "harness",
    "evolution",
    "external",
    "governance",
    "core",
    "data",
    "auth",
    "webhook",
    "addons",
]


def _body_statements(node) -> List[ast.stmt]:
    return [
        stmt
        for stmt in node.body
        if not (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )
    ]


def _is_passthrough(node) -> bool:
    body = _body_statements(node)
    if len(body) != 1:
        return False
    stmt = body[0]
    return isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call)


def scan(min_lines: int, include_passthrough: bool) -> List[Tuple[int, str, int, str, str]]:
    rows: List[Tuple[int, str, int, str, str]] = []
    for dir_name in CORE_DIRS:
        for path in (ROOT / dir_name).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name.startswith("__") or node.name.startswith("_test"):
                    continue
                lines = (node.end_lineno or node.lineno) - node.lineno + 1
                passthrough = include_passthrough and _is_passthrough(node)
                if lines <= min_lines or passthrough:
                    kind = "passthrough" if passthrough else "small"
                    rows.append(
                        (
                            lines,
                            str(path.relative_to(ROOT)).replace("\\", "/"),
                            node.lineno,
                            kind,
                            node.name,
                        )
                    )
    rows.sort(key=lambda r: (r[1], r[2]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="核心代码小方法扫描")
    parser.add_argument("--min-lines", type=int, default=3)
    parser.add_argument("--passthrough", action="store_true", help="同时列出纯转发方法")
    args = parser.parse_args()
    rows = scan(args.min_lines, args.passthrough)
    print(f"SMALL_METHOD_SCAN: {len(rows)} candidates (min_lines<={args.min_lines})")
    for lines, path, lineno, kind, name in rows:
        print(f"{lines:3} {path}:{lineno} {kind:11} {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
