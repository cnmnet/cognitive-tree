#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit logs and data files for leaked DeepSeek API keys."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"sk-[A-Za-z0-9]{20,}")
SKIP_DIRS = {".git", "__pycache__", "model_cache", "venv", "node_modules"}
SKIP_FILES = {".env", "security.key"}
ALLOWED_PREFIXES = (
    "sk-test-",
    "sk-user-",
    "sk-clear-",
    "sk-old-plain-",
    "sk-invalid-",
)


def audit() -> list:
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix not in (".log", ".json", ".txt", ".md", ".py"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in PATTERN.finditer(line):
                key = match.group(0)
                if key.startswith(ALLOWED_PREFIXES):
                    continue
                masked = key[:6] + "****" + key[-4:]
                hits.append((path.relative_to(ROOT).as_posix(), line_no, masked))
    return hits


def main() -> int:
    hits = audit()
    if not hits:
        print("SECRET_AUDIT: PASS")
        return 0
    print("SECRET_AUDIT: FAIL")
    for path, line_no, masked in hits:
        print(f"  {path}:{line_no} -> {masked}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
