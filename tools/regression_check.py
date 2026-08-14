#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无 GUI 回归闭环：测试 + pyflakes + 敏感文件扫描 + parity。"""

# 注意：parity 当前存在三个历史基线差异（重构前已存在）：
#   - AIClient.chat missing-key message differs
#   - build_debate_report_markdown differs
#   - Final debate report structure differs
# 它们与本次 access/application 重构无关，可用 --skip-parity 跳过单独排查。

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

PYFLAKES_MODULES = [
    "access/cli.py",
    "access/factory.py",
    "access/gui.py",
    "access/web.py",
    "access/web_services.py",
    "access/gui_parts/dialogs.py",
    "access/gui_parts/panels.py",
    "access/gui_parts/services.py",
    "access/gui_parts/views.py",
    "auth/__init__.py",
    "auth/services.py",
    "core/text_utils.py",
    "core/scoring.py",
    "data/services.py",
    "evolution/services.py",
    "evolution/godel.py",
    "evolution/meta_layer.py",
    "evolution/meta_search.py",
    "external/services.py",
    "external/summary.py",
    "governance/services.py",
    "governance/i18n.py",
    "harness/services.py",
    "webhook/__init__.py",
    "webhook/services.py",
    "tools/dependency_scan.py",
    "tools/dissolution_inventory.py",
    "tools/complexity_metrics.py",
    "tools/large_file_guard.py",
    "tools/qianfan_extractive_probe.py",
    "tools/qianfan_probe.py",
    "tools/report_quality_check.py",
    "tools/run_debate_token_compare.py",
    "tools/run_baseline.py",
    "tools/score_reports_eightdim.py",
    "tools/score_report_8dim.py",
    "tools/baseline_scoring.py",
    "tools/export_public.py",
    "tools/token_budget_check.py",
]
PYFLAKES_MODULES = [
    module for module in PYFLAKES_MODULES if (ROOT / module).exists()
]


def run(name: str, cmd: list, timeout: int = 300) -> bool:
    print(f"=== {name} ===", flush=True)
    try:
        proc = subprocess.run(cmd, cwd=ROOT, timeout=timeout)
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"{name}: TIMEOUT", flush=True)
        ok = False
    print(f"{name}: {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="无 GUI 回归闭环")
    parser.add_argument("--skip-parity", action="store_true", help="跳过 parity 检查")
    parser.add_argument(
        "--token-file",
        type=Path,
        default=None,
        help="可选：本次真实辩论的 token 汇总 JSON，检查是否超过预算基线",
    )
    args = parser.parse_args()

    results = []
    results.append(("pytest", run("pytest", [sys.executable, "-m", "pytest", "tests", "-q"])))
    results.append(("pyflakes", run("pyflakes", [sys.executable, "-m", "pyflakes"] + PYFLAKES_MODULES)))
    results.append(("secret_audit", run("secret_audit", [sys.executable, "tools/audit_secrets.py"])))
    results.append(("dependency_scan", run("dependency_scan", [sys.executable, "tools/dependency_scan.py"])))
    results.append(("complexity", run("complexity", [sys.executable, "tools/complexity_metrics.py", "--check"])))
    results.append(("large_file_guard", run("large_file_guard", [sys.executable, "tools/large_file_guard.py", "--check"])))
    results.append(("baseline_smoke", run("baseline_smoke", [sys.executable, "tools/run_baseline.py", "--smoke"])))
    results.append(("baseline_scoring", run("baseline_scoring", [sys.executable, "tools/baseline_scoring.py"])))
    if not args.skip_parity:
        results.append(("parity", run("parity", [sys.executable, "tools/parity_check.py"], timeout=600)))
    results.append(("report_quality", run("report_quality", [sys.executable, "tools/report_quality_check.py", "--self-test"])))
    if args.token_file is not None:
        results.append(
            (
                "token_budget",
                run(
                    "token_budget",
                    [
                        sys.executable,
                        "tools/token_budget_check.py",
                        "--file",
                        str(args.token_file),
                    ],
                ),
            )
        )

    print("\n=== 回归闭环汇总 ===", flush=True)
    failed = False
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}", flush=True)
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
