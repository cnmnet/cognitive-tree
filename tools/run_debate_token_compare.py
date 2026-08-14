#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实辩论对比运行器：跑单次完整辩论，记录 token 用量并输出压缩版报告。

用法：
    python tools/run_debate_token_compare.py \
        --root D:/路径/代码根目录 --label 新版 --out-dir D:/输出目录 \
        --env-file D:/路径/.env

设计为可跨版本使用：--root 指向旧版工作树即可用旧代码跑同一问题，
新旧版本各自输出完整报告、压缩版报告与 token 汇总 JSON。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_ROLES = [
    {"key": "radical", "name": "激进者", "instruction": "攻击默认前提，给出颠覆性方案。"},
    {"key": "conservative", "name": "保守者", "instruction": "风险优先，给出稳健方案。"},
    {"key": "structural", "name": "结构主义者", "instruction": "从已有晶体中寻找同构案例。"},
    {"key": "judge", "name": "大法官", "instruction": "依据晶体与原则做出终审裁决。"},
    {"key": "spokesperson", "name": "首席发言人", "instruction": "将辩论结论转化为清晰陈述。"},
    {"key": "lark", "name": "百灵鸟", "instruction": "补充外部世界知识。"},
    {"key": "pilgrim", "name": "取经者", "instruction": "锚定长期愿景与价值观。"},
    {"key": "strategist", "name": "奇谋者", "instruction": "捕捉机会窗口，敢押注非常规路径。"},
]


def load_env_file(path: Path) -> None:
    """只设置进程环境变量，不打印任何值。"""
    if not path or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value


def git_short_hash(root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            text=True,
        )
        return out.strip() or "unknown"
    except Exception:
        return "unknown"


def snippet(text: Any, limit: int) -> str:
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("…" if len(text) > limit else "")


def aggregate_tokens(logs: List[Dict]) -> Dict[str, Any]:
    totals = {
        "calls": len(logs),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
    }
    by_caller: Dict[str, Dict[str, Any]] = {}
    for entry in logs:
        caller = str(entry.get("caller") or "unknown")
        prompt = int(entry.get("prompt_tokens", 0) or 0)
        completion = int(entry.get("completion_tokens", 0) or 0)
        has_cache_fields = "prompt_cache_hit_tokens" in entry or "prompt_cache_miss_tokens" in entry
        if has_cache_fields:
            cache_hit = int(entry.get("prompt_cache_hit_tokens", 0) or 0)
            cache_miss = int(entry.get("prompt_cache_miss_tokens", 0) or 0)
        else:
            # 旧版 CALL_LOG 没有缓存字段，按全部未命中处理，避免命中率虚高。
            cache_hit = 0
            cache_miss = prompt
        totals["prompt_tokens"] += prompt
        totals["completion_tokens"] += completion
        totals["total_tokens"] += prompt + completion
        totals["prompt_cache_hit_tokens"] += cache_hit
        totals["prompt_cache_miss_tokens"] += cache_miss
        item = by_caller.setdefault(
            caller,
            {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 0,
            },
        )
        item["calls"] += 1
        item["prompt_tokens"] += prompt
        item["completion_tokens"] += completion
        item["total_tokens"] += prompt + completion
        item["prompt_cache_hit_tokens"] += cache_hit
        item["prompt_cache_miss_tokens"] += cache_miss
    for caller, item in by_caller.items():
        item["percent"] = round(item["total_tokens"] / totals["total_tokens"] * 100, 2) if totals["total_tokens"] else 0.0
    cache_sum = totals["prompt_cache_hit_tokens"] + totals["prompt_cache_miss_tokens"]
    totals["cache_hit_rate"] = round(totals["prompt_cache_hit_tokens"] / cache_sum * 100, 2) if cache_sum else 0.0
    return {"totals": totals, "by_caller": by_caller}


def role_views_from_rounds(rounds: List[Dict]) -> Dict[str, Dict[str, str]]:
    views: Dict[str, Dict[str, str]] = {}
    for rd in rounds:
        if rd.get("round", 0) == 0:
            continue
        for ans in rd.get("answers", []):
            role = str(ans.get("role", "未知"))
            views.setdefault(role, {})["last"] = str(ans.get("answer", ""))
            views.setdefault(role, {}).setdefault("first", str(ans.get("answer", "")))
    return views


def reflection_views(rounds: List[Dict]) -> List[Dict[str, str]]:
    result = []
    for rd in reversed(rounds):
        reflections = rd.get("reflection") or []
        if reflections:
            result = [
                {"role": str(item.get("role", "未知")), "answer": str(item.get("answer", ""))}
                for item in reflections
            ]
            break
    return result


def build_compressed_markdown(
    *,
    label: str,
    revision: str,
    question: str,
    elapsed: float,
    token_summary: Dict[str, Any],
    result: Dict[str, Any],
    full_report_path: Path,
    json_path: Path,
) -> str:
    lines = []
    lines.append(f"# 辩论对比 - {label}（压缩版）")
    lines.append("")
    lines.append(f"- 代码版本：`{revision}`")
    lines.append(f"- 问题：{question}")
    lines.append(f"- 耗时：{elapsed:.1f} 秒")
    lines.append(f"- 完整报告：{full_report_path}")
    lines.append(f"- 原始 JSON：{json_path}")
    lines.append("")

    totals = token_summary["totals"]
    lines.append("## Token 用量")
    lines.append("")
    lines.append(f"- 调用次数：{totals['calls']}")
    lines.append(f"- Prompt tokens：{totals['prompt_tokens']:,}")
    lines.append(f"- Completion tokens：{totals['completion_tokens']:,}")
    lines.append(f"- 总 tokens：{totals['total_tokens']:,}")
    lines.append(f"- 缓存命中 tokens：{totals.get('prompt_cache_hit_tokens', 0):,}")
    lines.append(f"- 缓存未命中 tokens：{totals.get('prompt_cache_miss_tokens', 0):,}")
    lines.append(f"- Prompt 缓存命中率：{totals.get('cache_hit_rate', 0.0):.1f}%")
    lines.append("")
    lines.append("| 调用方 | 次数 | Prompt | Completion | 合计 | 占比 | 缓存命中 | 缓存未命中 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for caller in sorted(token_summary["by_caller"], key=lambda c: -token_summary["by_caller"][c]["total_tokens"]):
        item = token_summary["by_caller"][caller]
        lines.append(
            f"| {caller} | {item['calls']} | {item['prompt_tokens']:,} | "
            f"{item['completion_tokens']:,} | {item['total_tokens']:,} | {item['percent']:.1f}% | "
            f"{item.get('prompt_cache_hit_tokens', 0):,} | {item.get('prompt_cache_miss_tokens', 0):,} |"
        )
    lines.append("")

    board = result.get("board_version", "")
    employee = result.get("employee_version", "")
    novice = result.get("novice_version", "")
    expert = result.get("expert_version", "")
    judge = result.get("judge_audit") or {}
    verdict = judge.get("final_verdict") or judge.get("summary", "")

    lines.append("## 老板版（节选 400 字）")
    lines.append("")
    lines.append(snippet(board, 400))
    lines.append("")
    lines.append("## 员工版（节选 350 字）")
    lines.append("")
    lines.append(snippet(employee, 350))
    lines.append("")
    lines.append("## 新人版（节选 300 字）")
    lines.append("")
    lines.append(snippet(novice, 300))
    lines.append("")
    lines.append("## 专家版（节选 500 字）")
    lines.append("")
    lines.append(snippet(expert, 500))
    lines.append("")
    lines.append("## 大法官终审裁决")
    lines.append("")
    lines.append(snippet(verdict, 500) or "（未返回终审裁决）")
    lines.append("")

    views = role_views_from_rounds(result.get("rounds", []))
    role_order = [
        "激进者", "保守者", "结构主义者", "百灵鸟", "取经者",
        "奇谋者", "延安智者", "大法官", "首席发言人",
    ]
    lines.append("## 角色核心观点（首轮 vs 末轮，各 100 字）")
    lines.append("")
    for role in role_order:
        if role not in views:
            continue
        first = snippet(views[role].get("first", ""), 100)
        last = snippet(views[role].get("last", ""), 100)
        lines.append(f"### {role}")
        lines.append("")
        lines.append(f"首轮：{first or '（无）'}")
        lines.append("")
        lines.append(f"末轮：{last or '（无）'}")
        lines.append("")

    reflections = reflection_views(result.get("rounds", []))
    if reflections:
        lines.append("## 反思声明（末轮，各 80 字）")
        lines.append("")
        for item in reflections:
            lines.append(f"**{item['role']}**：{snippet(item['answer'], 80)}")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="单次真实辩论 token 对比运行器")
    parser.add_argument("--root", type=Path, required=True, help="要运行的代码根目录")
    parser.add_argument("--label", required=True, help="运行标签，如 旧版/新版")
    parser.add_argument("--out-dir", type=Path, required=True, help="输出目录")
    parser.add_argument("--env-file", type=Path, default=None, help="额外 .env 文件（不打印内容）")
    parser.add_argument(
        "--question",
        default="如何设计一个多变量优化框架并评估综合策略，同时平衡长期目标与短期资源约束？",
    )
    parser.add_argument("--max-rounds", type=int, default=2)
    args = parser.parse_args()

    root = args.root.resolve()
    load_env_file(args.env_file)
    sys.path.insert(0, str(root))

    from external.ai_client import AIClient
    from data.storage import FileIO
    from governance.config import Config
    from harness.engine import CrystalEngine
    from harness.processors.debate import DebateEngine
    from harness.reporting import build_debate_report_markdown

    AIClient.CALL_LOG = []
    Config.DATA_ROOT = Config._determine_data_root()

    engine = CrystalEngine(FileIO())
    ai = AIClient()
    debate = DebateEngine(
        ai,
        engine,
        list(DEFAULT_ROLES),
        log=lambda message, level="system": print(f"[{level}] {str(message)[:120]}", flush=True),
        progress_callback=None,
    )

    print(f"\n=== 开始 {args.label} 辩论：{args.question[:40]}... ===", flush=True)
    started = time.time()
    result = debate.run(args.question, mode="debate_full", max_rounds=args.max_rounds)
    elapsed = time.time() - started

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^\w\-]+", "_", args.label)
    json_path = out_dir / f"{safe_label}_原始结果.json"
    full_md_path = out_dir / f"{safe_label}_完整报告.md"
    compressed_md_path = out_dir / f"{safe_label}_压缩版.md"
    token_path = out_dir / f"{safe_label}_token.json"
    calls_path = out_dir / f"{safe_label}_调用明细.json"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    full_md = build_debate_report_markdown(
        args.question,
        result,
        result.get("board_version", ""),
        result.get("employee_version", ""),
        result.get("novice_version", ""),
        result.get("expert_version", ""),
        result.get("judge_audit") or {},
    )
    full_md_path.write_text(full_md, encoding="utf-8")

    token_summary = aggregate_tokens(list(AIClient.CALL_LOG))
    token_summary["label"] = args.label
    token_summary["revision"] = git_short_hash(root)
    token_summary["question"] = args.question
    token_summary["elapsed_seconds"] = round(elapsed, 2)
    token_summary["generated_at"] = datetime.now().isoformat(timespec="seconds")
    token_path.write_text(json.dumps(token_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    calls_path.write_text(json.dumps(list(AIClient.CALL_LOG), ensure_ascii=False, indent=2), encoding="utf-8")

    compressed_md = build_compressed_markdown(
        label=args.label,
        revision=token_summary["revision"],
        question=args.question,
        elapsed=elapsed,
        token_summary=token_summary,
        result=result,
        full_report_path=full_md_path,
        json_path=json_path,
    )
    compressed_md_path.write_text(compressed_md, encoding="utf-8")

    print(
        json.dumps(
            {
                "label": args.label,
                "revision": token_summary["revision"],
                "elapsed_seconds": token_summary["elapsed_seconds"],
                "totals": token_summary["totals"],
                "compressed": str(compressed_md_path),
                "token": str(token_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
