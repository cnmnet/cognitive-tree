#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""10 题辩论基线跑分入口。

用法：
    python tools/run_baseline.py                 # 真实模型跑完整 10 题
    python tools/run_baseline.py --limit 3       # 只跑前 3 题（试跑/排障）
    python tools/run_baseline.py --smoke         # 离线冒烟：合成辩论结果，无网络无 Key
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.scoring import score_payload
from data.storage import FileIO
from governance.config import Config
from harness.engine import CrystalEngine
from harness.processors.debate import DebateEngine
from harness.processors.planner import BaselineRunner


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


def load_roles() -> list:
    roles_path = ROOT / "晶体树文件夹" / "核心配置" / "角色定义.json"
    if not roles_path.exists():
        return DEFAULT_ROLES
    try:
        raw = json.loads(roles_path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_ROLES
    roles = [
        {"key": key, "name": value.get("name", key), "instruction": value.get("instruction", "")}
        for key, value in raw.items()
    ]
    return roles or DEFAULT_ROLES


def _synthetic_debate_result(question: str, **kwargs) -> dict:
    """离线冒烟用的确定性辩论结果，覆盖 BaselineRunner 全部指标分支。"""
    return {
        "rounds": [
            {
                "round": 1,
                "answers": [
                    {"role": "激进者", "answer": "[C001] 通过机制设计提升决策质量。"},
                    {"role": "保守者", "answer": "[H001] 控制成本并保留止损路径。"},
                ],
                "audit": {
                    "feedback_by_role": {"激进者": "请补充证据与边界。", "保守者": "建议给出可量化指标。"},
                    "disagreement_map": {"risk": True, "cost": True, "evidence": False},
                    "evidence_scores": {"激进者": 0.7, "保守者": 0.5},
                },
            },
            {
                "round": 2,
                "answers": [
                    {"role": "激进者", "answer": "[C001] 先建立诊断机制，再分三步执行，并识别主要风险。"},
                    {"role": "保守者", "answer": "[H001] 建议采用步骤化方案，控制预算与时间节点，同时设置止损。"},
                ],
                "audit": {
                    "feedback_by_role": {"激进者": "方案可行，请补充风险与止损。", "保守者": "可以执行。"},
                    "disagreement_map": {"risk": True, "cost": False, "evidence": True},
                    "evidence_scores": {"激进者": 0.8, "保守者": 0.6},
                },
            },
        ],
        "final": {
            "one_sentence_conclusion": "用诊断机制打破惯性。",
            "student_friendly_answer": "建议先诊断、再分步骤执行，同时识别风险并给出止损方案。",
            "teacher_detail": "本方案包含可执行步骤，并明确列出风险边界与止损机制。",
        },
    }


def _detail_score_text(detail: dict) -> str:
    raw = detail.get("raw_final") or {}
    parts = []
    rigid = raw.get("rigid_core") or {}
    for key in ("decision_summary", "key_synthesis"):
        value = rigid.get(key)
        if value:
            parts.append(str(value))
    for key in ("soft_wrap", "one_sentence_conclusion", "student_friendly_answer", "teacher_detail"):
        value = raw.get(key)
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def attach_scores(data: dict) -> None:
    for detail in data.get("details", []):
        detail["score"] = score_payload(_detail_score_text(detail))


def print_score_summary(data: dict) -> None:
    details = data.get("details", [])
    print("\n=== 八维评分汇总 ===")
    if not details:
        print("无有效明细")
        return
    print("| # | 问题 | 综合总分 |")
    print("| --- | --- | ---: |")
    totals = []
    for idx, detail in enumerate(details, 1):
        total = (detail.get("score") or {}).get("total", 0)
        totals.append(total)
        print(f"| {idx} | {detail.get('question', '')[:38]} | {total} |")
    if totals:
        print(f"\n平均综合总分：{round(sum(totals) / len(totals), 1)}")


def run_smoke(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    class _OfflineAI:
        api_key = ""

        def chat(self, prompt, system=None, temperature=0.5, **kwargs):
            return "离线冒烟回答。"

        def chat_json(self, prompt, temperature=0.3, **kwargs):
            return {}

    output_path = output_dir / "辩论基线.smoke.json"
    engine = CrystalEngine(FileIO())
    runner = BaselineRunner(engine, _OfflineAI(), load_roles())
    with mock.patch.object(DebateEngine, "run", side_effect=_synthetic_debate_result):
        data = runner.run(max_rounds=2, question_limit=1, output_path=output_path)
    attach_scores(data)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print_score_summary(data)
    summary = data.get("summary", {})
    if not output_path.exists() or summary.get("total_valid") != 1:
        print("BASELINE_SMOKE: FAIL", flush=True)
        return 1
    print(
        json.dumps(
            {
                "smoke": "PASS",
                "questions": data.get("total_questions"),
                "jaccard": summary.get("jaccard_similarity"),
                "output": str(output_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="10 题辩论基线跑分")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 题")
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON 输出路径（默认写入数据根目录 系统日志/辩论基线.json）",
    )
    parser.add_argument("--smoke", action="store_true", help="离线冒烟模式")
    args = parser.parse_args()

    if args.smoke:
        with tempfile.TemporaryDirectory(prefix="baseline_smoke_") as tmp:
            return run_smoke(Path(tmp))

    output_path = args.output
    if output_path is None:
        output_path = Config.DATA_ROOT / "系统日志" / "辩论基线.json"

    engine = CrystalEngine(FileIO())
    from external.ai_client import AIClient

    ai = AIClient()
    runner = BaselineRunner(engine, ai, load_roles())
    data = runner.run(max_rounds=args.max_rounds, question_limit=args.limit, output_path=output_path)
    attach_scores(data)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print_score_summary(data)
    print(
        json.dumps(
            {
                "mode": "live",
                "questions": data.get("total_questions"),
                "summary": data.get("summary"),
                "output": str(output_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
