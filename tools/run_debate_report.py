#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a real multi-role debate through v5 and save original + compressed reports."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

from access.factory import _build_meta_dependencies

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.storage import FileIO
from evolution.meta_layer import MetaLayer
from external.ai_client import AIClient
from governance.config import Config
from harness.engine import CrystalEngine
from harness.processors.debate import DebateEngine
from harness.reporting import (
    build_debate_report_markdown,
    build_quick_view_report,
    limit_original_report,
    polish_report_markdown,
)


QUESTION = """你是“认知晶体树·因材施教版”的教学教研引擎。请基于同一篇作文，面向以下 5 位水平不同的学生，分别输出五版差异化教学反馈，并输出 1 份班级教学建议。

【作文题目】《难忘的一次尝试》（小学高年级记叙文，约 350 字）

【学生作文】
那天，我第一次学骑自行车。一开始我不敢上车，爸爸在后面扶着。我骑了几步，车把摇来摇去，差点摔倒。爸爸说：“别怕，眼睛看前面。”我试了很多次，终于可以骑一段路了。我特别开心，觉得只要勇敢，就能学会新东西。晚上回到家，我把这件事写下来，想记住这一天。

【5 位学生画像】
A：基础扎实，描写细腻，但结尾升华不足，容易写成“道理式收尾”。
B：构思新颖，想法多，但段落结构松散，详略不当。
C：语言平实，缺少动作和心理细节，叙述像流水账。
D：写作能力优秀，需要更高立意和更高级的谋篇布局挑战。
E：基础薄弱，句子不够通顺，需要保护信心、先补基础。

【输出要求】
1. 教师速览版：30 秒看清 5 人差异，用表格呈现“当前卡点 / 最大亮点 / 下一步只做一件事”。
2. 教学操作版：下周分层教学建议，明确 3 个小组分别练什么、怎么练、用什么标准验收。
3. 家长版：每个孩子 2-3 个在家可做的动作，不说术语，不制造焦虑。
4. 学生版：每人 1 段温暖、具体、可执行的修改建议，必须引用作文原文中的证据。
5. 专家版：对标课标维度（选材、结构、语言、立意）逐项评分与依据。
6. 班级报告：全班共性错误、分层分组建议、下一次写作训练重点。

【硬性约束】
- 评语只能引用作文原文中的事实，禁止无据断言。
- 不贴“差生/天才”标签，不承诺分数。
- 同班必须同一把尺子：评分标准一致，只是要求分层。
- 输出完整 Markdown，不要遗漏任何一版。"""


ROLES = [
    {"key": "radical", "name": "激进者", "instruction": "攻击默认前提，假设现有框架是错的，给出颠覆性方案。"},
    {"key": "conservative", "name": "保守者", "instruction": "风险优先，假设资源有限，给出最可落地的稳健方案。"},
    {"key": "structural", "name": "结构主义者", "instruction": "从已有晶体中寻找同构案例，用类比生成方案。"},
    {"key": "judge", "name": "大法官", "instruction": "以晶体卡片、核心操作原则和资源约束为准绳，做出终审裁决。必须明确引用依据。"},
    {"key": "spokesperson", "name": "首席发言人", "instruction": "将内部辩论结论转化为清晰、简洁、无歧义的对外陈述。"},
    {"key": "lark", "name": "百灵鸟", "instruction": "从外部世界补充信息，打破信息茧房。"},
    {"key": "pilgrim", "name": "取经者", "instruction": "以长期愿景和核心价值观为锚，防止短期利益偏离使命。"},
    {"key": "strategist", "name": "奇谋者", "instruction": "善于洞察人心、把握时机，敢押注非常规路径。"},
    {"key": "statesman", "name": "延安智者", "instruction": "坚持调查研究，从全局矛盾和主要矛盾切入，提出可落地的综合方略。"},
]


def main() -> int:
    if not Config.get_api_key():
        print("DEEPSEEK_API_KEY 未设置")
        return 1

    ai = AIClient()
    engine = CrystalEngine(FileIO())
    force_factory, providers, planner_factory = _build_meta_dependencies()
    engine.meta = MetaLayer(
        engine,
        FileIO(),
        ai_client=ai,
        force_explorer_factory=force_factory,
        anti_fraud_providers=providers,
        planner_factory=planner_factory,
    )
    debate = DebateEngine(
        ai,
        engine,
        ROLES,
        log=lambda message, level="system": print(f"[{level}] {message}", flush=True),
    )
    debate.rumad_enabled = False

    print("多角色辩论进行中...", flush=True)
    result = debate.run(QUESTION, mode="debate_full", max_rounds=2)
    schema = result.get("final_schema", {}) or {}
    judge_audit = schema.get("judge_audit", {}) or result.get("judge_audit", {}) or {}

    print("生成原始版报告...", flush=True)
    original = build_debate_report_markdown(
        QUESTION,
        result,
        schema.get("board_version", ""),
        schema.get("employee_version", ""),
        schema.get("novice_version", ""),
        schema.get("expert_version", ""),
        judge_audit,
    )
    original = limit_original_report(original, ai_client=ai)
    print(f"原始版长度: {len(original)}", flush=True)

    print("生成压缩版报告...", flush=True)
    compressed = polish_report_markdown(original, ai_client=ai, max_len=5000)
    print(f"压缩版长度: {len(compressed)}", flush=True)

    print("生成速览版报告...", flush=True)
    quick = build_quick_view_report(original, ai_client=ai)
    print(f"速览版长度: {len(quick)}", flush=True)

    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home() / "桌面"
    desktop.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    original_path = desktop / f"辩论报告_原始版_多角色_教育测试_{stamp}.md"
    compressed_path = desktop / f"辩论报告_压缩版_多角色_教育测试_{stamp}.md"
    quick_path = desktop / f"辩论报告_速览版_多角色_教育测试_{stamp}.md"
    original_path.write_text(original, encoding="utf-8")
    compressed_path.write_text(compressed, encoding="utf-8")
    quick_path.write_text(quick, encoding="utf-8")

    print("ORIG=" + str(original_path))
    print("COMP=" + str(compressed_path))
    print("QUICK=" + str(quick_path))
    print("CALL_COUNT=" + str(ai._call_count))
    print("TOKEN_ESTIMATE=" + str(ai._token_estimate))
    return 0


if __name__ == "__main__":
    sys.exit(main())
