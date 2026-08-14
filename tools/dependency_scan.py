#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核心模块依赖扫描：检查模块间依赖方向是否符合目标架构。"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACKAGES = [
    "access",
    "harness",
    "evolution",
    "core",
    "data",
    "external",
    "governance",
    "addons",
    "auth",
    "webhook",
]

ALLOWED = {
    "access": {"core", "data", "evolution", "external", "governance", "harness"},
    "harness": {"core", "data", "external", "governance"},
    "evolution": {"core", "data", "external", "governance"},
    "data": {"core", "governance"},
    "external": {"core", "governance"},
    "core": set(),
    "governance": set(),
    "addons": {"core", "data", "external", "governance", "harness"},
    "auth": set(),
    "webhook": {"auth"},
}

# 已知待解耦边：刀3/4/5 处理，默认不判失败，--strict 时判失败。
PENDING_EXCEPTIONS = {
    ("harness", "evolution"),
    ("evolution", "harness"),
}

ACCESS_ALLOWED_MODULES = {
    "auth.services",
    "data.services",
    "evolution.services",
    "external.services",
    "governance.services",
    "harness.services",
    "webhook.services",
}
ACCESS_COMPOSITION_PATHS = {"access/dependencies.py", "access/factory.py"}


def collect_imports() -> dict:
    graph = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for pkg in PACKAGES:
        for path in (ROOT / pkg).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            rel = path.relative_to(ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    top = name.split(".")[0]
                    if top in PACKAGES and top != pkg:
                        graph[pkg][top][rel].add(name)
    return {
        pkg: {
            dep: {
                path: sorted(modules) for path, modules in paths.items()
            }
            for dep, paths in deps.items()
        }
        for pkg, deps in graph.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="核心模块依赖扫描")
    parser.add_argument("--strict", action="store_true", help="待解耦边也判失败")
    args = parser.parse_args()

    graph = collect_imports()
    violations = []
    pending = []
    for pkg, deps in graph.items():
        for dep, paths in deps.items():
            for path, modules in paths.items():
                if pkg == "access":
                    if path in ACCESS_COMPOSITION_PATHS:
                        continue
                    if any(module in ACCESS_ALLOWED_MODULES for module in modules):
                        continue
                    violations.append((pkg, dep, path, modules))
                    continue
                if dep not in ALLOWED.get(pkg, set()):
                    if (pkg, dep) in PENDING_EXCEPTIONS:
                        pending.append((pkg, dep, path, modules))
                    else:
                        violations.append((pkg, dep, path, modules))

    print("DEPENDENCY_SCAN: " + ("FAIL" if violations else "PASS"))
    for pkg, dep, path, modules in sorted(violations):
        print(f"  VIOLATION: {pkg} -> {dep} ({path})")
        for module in modules:
            print(f"    {module}")
    if pending:
        print("  PENDING:")
        for pkg, dep, path, modules in sorted(pending):
            print(f"    {pkg} -> {dep} ({path})")
            for module in modules:
                print(f"      {module}")
    return 1 if violations else (1 if args.strict and pending else 0)


if __name__ == "__main__":
    raise SystemExit(main())
