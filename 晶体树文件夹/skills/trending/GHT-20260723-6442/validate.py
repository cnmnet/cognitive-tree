#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Trending 晶体验证脚本"""
import sys

def validate(content: str) -> dict:
    checks = {
        "has_content": bool(content and content.strip()),
        "length_ok": 10 <= len(content) <= 500,
    }
    score = sum(1 for v in checks.values() if v) / len(checks)
    return {"valid": score >= 0.75, "checks": checks, "score": round(score, 2)}
