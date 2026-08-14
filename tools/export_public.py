#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成不含 GUI 与敏感文件的公开版源码目录（dist_public/）。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist_public"

PACKAGE_DIRS = [
    "access",
    "auth",
    "webhook",
    "core",
    "data",
    "evolution",
    "external",
    "governance",
    "harness",
    "addons",
    "web_static",
    "i18n",
    "tests",
    "tools",
]

ROOT_FILES = [
    "pyproject.toml",
    "MANIFEST.in",
    "README.md",
    "LICENSE",
    ".gitignore",
    "requirements.txt",
    "requirements-server.txt",
    ".env.example",
    "main.py",
]


def _ignore_gui_and_runtime(src, names):
    ignored = {
        "__pycache__",
        ".pytest_cache",
        ".env",
        "security.key",
        "dist_public",
        "晶体树文件夹",
        "暂存区",
        "系统日志",
    }
    ignored.update({name for name in names if name.endswith(".log")})
    ignored.update({name for name in names if name.endswith(".egg-info")})
    if Path(src).name == "access":
        ignored.update({"gui.py", "gui_parts"})
    if Path(src).name == "tools":
        ignored.add("reference")
    if Path(src).name == "tests":
        ignored.add("test_access_gui.py")
    if Path(src).name == "web_static":
        ignored.update({name for name in names if " - 副本" in name})
    if Path(src).name in ("docs", "i18n"):
        if Path(src).name == "docs":
            ignored.update({"输出"})
    return ignored


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for dir_name in PACKAGE_DIRS:
        src = ROOT / dir_name
        if src.exists():
            shutil.copytree(
                src,
                OUT / dir_name,
                ignore=_ignore_gui_and_runtime,
            )
    for name in ROOT_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, OUT / name)
    (OUT / "PUBLIC_BUILD.txt").write_text(
        "公开版不含 GUI 源码、旧版 parity 参考、环境密钥与运行时数据。\n"
        "Public build: no GUI source, no parity reference, no secrets, no runtime data.\n",
        encoding="utf-8",
    )
    forbidden = [
        OUT / "access" / "gui.py",
        OUT / "access" / "gui_parts",
        OUT / "tools" / "reference",
        OUT / ".env",
        OUT / "security.key",
    ]
    problems = []
    for path in forbidden:
        if path.exists():
            problems.append(str(path.relative_to(OUT)))
    problems.extend(
        str(path.relative_to(OUT))
        for path in OUT.rglob("*")
        if path.is_file()
        and (
            path.suffix in (".db", ".sqlite3")
            or path.name == ".env"
            or path.name == "security.key"
        )
    )
    if problems:
        print("PUBLIC_EXPORT: FAIL")
        for item in sorted(set(problems)):
            print(f"  FORBIDDEN: {item}")
        return 1
    print(f"PUBLIC_EXPORT: {OUT}")
    print("PUBLIC_EXPORT: PASS (no GUI / secrets / parity reference)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
