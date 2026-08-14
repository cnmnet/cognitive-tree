#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""输出报告质量门禁：五版本章节 + 各角色压缩内容。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List


DEFAULT_ROLES = [
    "激进者", "保守者", "结构主义者", "百灵鸟", "取经者",
    "奇谋者", "延安智者", "大法官", "首席发言人",
]
VERSION_MARKERS = ["老板版", "员工版", "新人版", "专家版", "儒雅笔谈"]


def check_report(text: str, required_roles: List[str] = None) -> List[str]:
    """返回缺失章节列表；为空表示通过。"""
    missing = []
    roles = required_roles or DEFAULT_ROLES
    for marker in VERSION_MARKERS:
        if marker not in text:
            missing.append(f"缺少版本章节：{marker}")
    for role in roles:
        if f"### {role}" not in text:
            missing.append(f"缺少角色压缩内容：{role}")
    return missing


def _self_test() -> int:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from harness.reporting import build_debate_report_markdown

    question = "测试问题"
    rounds = [
        {
            "round": 1,
            "answers": [
                {"role": role, "answer": f"{role} 的压缩观点。"}
                for role in DEFAULT_ROLES
            ],
        }
    ]
    result = {
        "rounds": rounds,
        "elegant_epilogue": "儒雅笔谈内容。",
    }
    judge_audit = {
        "role_scorecard": [
            {
                "role": role,
                "contribution_percent": 10,
                "status": "adopted",
                "brief_reason": "可行",
            }
            for role in DEFAULT_ROLES
        ],
        "final_verdict": "终审裁决。",
    }
    report = build_debate_report_markdown(
        question,
        result,
        "老板版内容。",
        "员工版内容。",
        "新人版内容。",
        "专家版内容。",
        judge_audit,
    )
    missing = check_report(report)
    if missing:
        print("REPORT_QUALITY: FAIL")
        for item in missing:
            print(f"  - {item}")
        return 1
    print("REPORT_QUALITY: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="输出报告质量门禁")
    parser.add_argument("--file", type=Path, action="append", help="要检查的 Markdown 报告（可多次）")
    parser.add_argument("--roles", default="", help="逗号分隔的必需角色列表（默认全角色）")
    parser.add_argument("--self-test", action="store_true", help="用生成器自检门禁是否可用")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    required_roles = [r.strip() for r in args.roles.split(",") if r.strip()] or None
    failed = False
    for path in args.file or []:
        text = path.read_text(encoding="utf-8")
        missing = check_report(text, required_roles)
        if missing:
            failed = True
            print(f"REPORT_QUALITY: FAIL {path}")
            for item in missing:
                print(f"  - {item}")
        else:
            print(f"REPORT_QUALITY: PASS {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
