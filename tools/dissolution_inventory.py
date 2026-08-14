#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""application 脚手架拆解盘点：只读分析函数归属与搬迁量，不改代码。"""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CAT_BUSINESS = "业务"
CAT_UI = "UI壳"
CAT_SYSTEM = "系统"


HOME_MAP = {
    "normalize_text": ("harness", CAT_BUSINESS),
    "existing_crystal_ids": ("harness", CAT_BUSINESS),
    "similar_crystals": ("harness", CAT_BUSINESS),
    "build_crystallization_prompt": ("harness", CAT_BUSINESS),
    "normalize_crystal_response": ("harness", CAT_BUSINESS),
    "append_pending_card": ("harness", CAT_BUSINESS),
    "update_files": ("harness", CAT_BUSINESS),
    "assets": ("harness", CAT_BUSINESS),
    "pending_cards": ("harness", CAT_BUSINESS),
    "task_cards": ("harness", CAT_BUSINESS),
    "save_task_cards": ("harness", CAT_BUSINESS),
    "load_roles": ("governance", CAT_BUSINESS),
    "get_fingerprint": ("harness", CAT_BUSINESS),
    "submit_hebbian_reward": ("harness", CAT_BUSINESS),
    "get_hebbian_stats": ("harness", CAT_BUSINESS),
    "patch_asset": ("harness", CAT_BUSINESS),
    "delete_asset": ("harness", CAT_BUSINESS),
    "confirm_pending_card": ("harness", CAT_BUSINESS),
    "ignore_pending_card": ("harness", CAT_BUSINESS),
    "list_sessions": ("data", CAT_BUSINESS),
    "ensure_session": ("data", CAT_BUSINESS),
    "add_session_message": ("data", CAT_BUSINESS),
    "history_context": ("data", CAT_BUSINESS),
    "question_history": ("data", CAT_BUSINESS),
    "system_status": ("harness", CAT_BUSINESS),
    "holes_snapshot": ("harness", CAT_BUSINESS),
    "today_snapshot": ("harness", CAT_BUSINESS),
    "system_health": ("harness", CAT_BUSINESS),
    "health_dashboard": ("harness", CAT_BUSINESS),
    "search_documents": ("external", CAT_BUSINESS),
    "extract_keywords": ("external", CAT_BUSINESS),
    "sync_vector_store": ("external", CAT_BUSINESS),
    "create_checkout_session": ("webhook", CAT_BUSINESS),
    "get_trending": ("external", CAT_BUSINESS),
    "refresh_trending": ("external", CAT_BUSINESS),
    "get_radar": ("external", CAT_BUSINESS),
    "vector_status": ("external", CAT_BUSINESS),
    "get_conflicts": ("external", CAT_BUSINESS),
    "create_session_record": ("data", CAT_BUSINESS),
    "get_session_record": ("data", CAT_BUSINESS),
    "rename_session_record": ("data", CAT_BUSINESS),
    "delete_session_record": ("data", CAT_BUSINESS),
    "clear_session_record": ("data", CAT_BUSINESS),
    "list_skills": ("harness", CAT_BUSINESS),
    "get_skill": ("harness", CAT_BUSINESS),
    "validate_skills": ("harness", CAT_BUSINESS),
    "validate_single_skill": ("harness", CAT_BUSINESS),
    "resolve_task": ("harness", CAT_BUSINESS),
    "ignore_task": ("harness", CAT_BUSINESS),
    "run_chat_task": ("harness", CAT_BUSINESS),
    "run_crystallize_task": ("harness", CAT_BUSINESS),
    "run_file_chat_task": ("harness", CAT_BUSINESS),
    "run_batch_process_task": ("harness", CAT_BUSINESS),
    "run_daily_plan_task": ("harness", CAT_BUSINESS),
    "run_deep_reasoning_task": ("harness", CAT_BUSINESS),
    "JobManager": ("access", CAT_SYSTEM),
    "LegacyProcessManager": ("access", CAT_SYSTEM),
    "register_user": ("auth", CAT_BUSINESS),
    "login_user": ("auth", CAT_BUSINESS),
    "current_user_info": ("auth", CAT_BUSINESS),
    "update_user_api_key": ("auth", CAT_BUSINESS),
    "clear_user_api_key": ("auth", CAT_BUSINESS),
    "delete_user_account": ("auth", CAT_BUSINESS),
    "privacy_content": ("auth", CAT_BUSINESS),
    "run_skill_migration": ("harness", CAT_BUSINESS),
    "check_ai_access": ("auth", CAT_BUSINESS),
    "user_effective_key": ("auth", CAT_BUSINESS),
    "is_complex_question": ("harness", CAT_BUSINESS),
    "build_performance_table": ("harness", CAT_BUSINESS),
    "save_report_to_desktop": ("harness", CAT_BUSINESS),
    "current_profile": ("governance", CAT_BUSINESS),
    "load_debate_roles": ("governance", CAT_BUSINESS),
    "format_crystal_update_preview": ("harness", CAT_BUSINESS),
    "build_pending_card_view_data": ("harness", CAT_BUSINESS),
    "polish_report": ("harness", CAT_BUSINESS),
    "generate_dual_titles": ("harness", CAT_BUSINESS),
    "generate_round_label_simple": ("harness", CAT_BUSINESS),
    "build_elegant_narrative_prompt": ("harness", CAT_BUSINESS),
    "generate_elegant_narrative": ("harness", CAT_BUSINESS),
    "clamp_debate_rounds": ("harness", CAT_BUSINESS),
    "build_session_context": ("harness", CAT_BUSINESS),
    "run_gui_chat_task": ("harness", CAT_BUSINESS),
    "run_gui_crystal_task": ("harness", CAT_BUSINESS),
    "run_godel_evolution": ("evolution", CAT_BUSINESS),
    "run_recursive_evolution": ("evolution", CAT_BUSINESS),
    "run_anti_fraud_audit": ("evolution", CAT_BUSINESS),
    "run_gui_batch_task": ("harness", CAT_BUSINESS),
    "wisdom_commons_display": ("harness", CAT_BUSINESS),
    "run_gui_daily_plan": ("harness", CAT_BUSINESS),
    "force_self_healing": ("evolution", CAT_BUSINESS),
    "run_gui_file_chat_task": ("harness", CAT_BUSINESS),
    "force_archive_holes": ("harness", CAT_BUSINESS),
    "run_sync_vector_store": ("external", CAT_BUSINESS),
    "run_meta_search": ("evolution", CAT_BUSINESS),
    "run_auto_health_fix": ("harness", CAT_BUSINESS),
    "restore_original_sessions": ("data", CAT_BUSINESS),
    "run_validate_skills": ("harness", CAT_BUSINESS),
    "run_contribute_crystal": ("harness", CAT_BUSINESS),
    "run_inherit_seeds": ("harness", CAT_BUSINESS),
    "run_force_exploration": ("evolution", CAT_BUSINESS),
    "run_external_fetch": ("external", CAT_BUSINESS),
    "run_inspiration_phase2": ("evolution", CAT_BUSINESS),
    "daily_plan_is_run_today": ("harness", CAT_BUSINESS),
    "duckduckgo_search": ("external", CAT_BUSINESS),
    "run_skill_migration_gui": ("harness", CAT_BUSINESS),
    "run_single_deep_reasoning": ("harness", CAT_BUSINESS),
    "run_debate_engine_reasoning": ("harness", CAT_BUSINESS),
    "simple_keywords": ("harness", CAT_BUSINESS),
    "parse_keyword_input": ("harness", CAT_BUSINESS),
    "similar_crystal_pairs": ("harness", CAT_BUSINESS),
    "build_saturation_status_text": ("access/gui_parts", CAT_UI),
    "build_skill_status_text": ("access/gui_parts", CAT_UI),
    "build_wisdom_stats_text": ("access/gui_parts", CAT_UI),
    "build_rumad_status_text": ("access/gui_parts", CAT_UI),
    "build_exploration_status_text": ("access/gui_parts", CAT_UI),
    "build_godel_status_text": ("access/gui_parts", CAT_UI),
    "build_pareto_report_text": ("access/gui_parts", CAT_UI),
    "build_cognitive_efficiency_text": ("access/gui_parts", CAT_UI),
    "build_failure_patterns_text": ("access/gui_parts", CAT_UI),
    "build_dual_loop_report_text": ("access/gui_parts", CAT_UI),
    "build_inspiration_furnace_text": ("access/gui_parts", CAT_UI),
    "vote_role": ("harness", CAT_BUSINESS),
    "parse_pending_card_block": ("harness", CAT_BUSINESS),
    "confirm_pending_card_with_content": ("harness", CAT_BUSINESS),
    "run_skill_export": ("harness", CAT_BUSINESS),
    "create_twin_workbench": ("harness", CAT_BUSINESS),
    "update_skill_content": ("harness", CAT_BUSINESS),
    "update_gui_files": ("harness", CAT_BUSINESS),
}


def line_count(node: ast.AST) -> int:
    return node.end_lineno - node.lineno + 1


def analyze_services() -> list:
    path = ROOT / "application" / "services.py"
    if not path.exists():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    items = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        home, cat = HOME_MAP.get(node.name, ("待定", CAT_BUSINESS))
        items.append(
            {
                "file": "application/services.py",
                "name": node.name,
                "kind": type(node).__name__.replace("Def", ""),
                "start": node.lineno,
                "end": node.end_lineno,
                "lines": line_count(node),
                "category": cat,
                "home": home,
            }
        )
    return items


def analyze_scaffold_files() -> list:
    items = []
    for path in (
        ROOT / "application" / "backend.py",
        ROOT / "application" / "factory.py",
        ROOT / "application" / "__init__.py",
    ):
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                items.append(
                    {
                        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "name": node.name,
                        "kind": type(node).__name__.replace("Def", ""),
                        "start": node.lineno,
                        "end": node.end_lineno,
                        "lines": line_count(node),
                        "category": CAT_SYSTEM,
                        "home": "access",
                    }
                )
    return items


def summarize(items: list) -> dict:
    by_home = defaultdict(int)
    by_category = defaultdict(int)
    for item in items:
        by_home[item["home"]] += item["lines"]
        by_category[item["category"]] += item["lines"]
    return {
        "items": items,
        "by_home": dict(sorted(by_home.items(), key=lambda kv: -kv[1])),
        "by_category": dict(by_category),
        "total_lines": sum(item["lines"] for item in items),
    }


def to_markdown(data: dict) -> str:
    today = date.today().isoformat()
    lines = [
        "# application 脚手架拆解清单",
        "",
        f"- 生成日期：{today}",
        "- 说明：只读分析，未修改任何代码。",
        "",
        "## 总览",
        "",
        f"- 拆解对象总行数：{data['total_lines']}",
        f"- 业务逻辑行数：{data['by_category'].get('业务', 0)}",
        f"- UI壳/系统行数：{data['by_category'].get('UI壳', 0) + data['by_category'].get('系统', 0)}",
        "",
        "## 按最终归属",
        "",
        "| 归属 | 行数 |",
        "| --- | ---: |",
    ]
    for home, count in data["by_home"].items():
        lines.append(f"| {home} | {count} |")
    lines.extend(["", "## 明细", "", "| 文件 | 名称 | 类型 | 起止行 | 行数 | 类别 | 归属 |", "| --- | --- | --- | --- | ---: | --- | --- |"])
    for item in data["items"]:
        lines.append(
            f"| {item['file']} | {item['name']} | {item['kind']} | "
            f"{item['start']}-{item['end']} | {item['lines']} | "
            f"{item['category']} | {item['home']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    items = analyze_services() + analyze_scaffold_files()
    data = summarize(items)
    report_md = ROOT / "docs" / f"dissolution_inventory_{date.today().strftime('%Y%m%d')}.md"
    report_json = report_md.with_suffix(".json")
    report_md.write_text(to_markdown(data), encoding="utf-8")
    report_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "by_home": data["by_home"],
                "by_category": data["by_category"],
                "total_lines": data["total_lines"],
                "report_md": str(report_md),
                "report_json": str(report_json),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
