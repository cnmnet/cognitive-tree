#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""access 层迁移盘点：只读分析 GUI/Web 的函数归属与搬迁量，不改现有代码。"""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CAT_SERVICE = "业务逻辑"
CAT_UI = "界面壳"
CAT_MIXED = "混合"


GUI_SERVICE = {
    "_do_chat", "_chat_done", "_handle_title_generation_after_reply",
    "_generate_dual_titles", "_generate_round_label_simple", "_existing_crystal_ids",
    "_shorten_crystal_content", "_build_crystallization_prompt",
    "_normalize_crystal_response", "_find_similar_crystals",
    "_format_crystal_update_preview", "_commit_crystal_update", "_do_crystal",
    "_do_gödel_evolution", "_gödel_evolution_done", "_do_recursive_evolution",
    "_recursive_evolution_done", "_do_force_self_healing", "_do_anti_fraud_audit",
    "_anti_fraud_audit_done", "_append_audit_report", "_crystal_done",
    "_do_deep_reasoning", "_single_deep_reasoning", "_save_report_to_desktop",
    "_debate_engine_reasoning", "_create_pending_from_competition", "_do_file_chat",
    "_file_chat_done", "_start_batch", "_stop_batch_process", "_batch_done",
    "_do_force_archive", "_extract_pending_content", "_ask_daily_keywords",
    "_run_daily_plan_thread", "_stop_daily_plan", "_load_task_cards",
    "_save_task_cards", "_check_and_run_daily_plan", "_manual_run_daily_plan",
    "_extract_keywords", "_search_duckduckgo", "_append_pending_card",
    "_update_files", "_update_skill_content", "_load_roles", "_init_app",
    "_sync_vector_store", "_do_meta_search", "_export_agents_md",
    "_export_all_skills", "_get_current_profile", "_do_migrate_to_skills",
    "_do_validate_skills", "_do_contribute_crystal", "_contribute_done",
    "_do_inherit_seeds", "_inherit_done", "_toggle_rumad",
    "_do_force_exploration", "_force_exploration_done", "_do_external_fetch",
    "_external_fetch_done", "_do_inspiration_phase2", "_inspiration_phase2_done",
    "_polish_report", "_generate_elegant_narrative", "_is_complex_question",
    "_get_debate_rounds", "_sync_debate_round_state", "_build_session_context",
    "_load_session_list", "_vote", "_do_auto_health_fix",
    "_restore_original_sessions",
}

GUI_MIXED = {
    "_show_deposit_popup", "_show_role_vote_popup", "_preview_crystal_update",
    "_output_debate_report", "_stream_elegant_with_typewriter",
    "_open_twin_workbench", "_confirm_pending_card",
    "_confirm_pending_card_with_content", "_read_edit_and_commit_pending",
    "_export_skill_dialog", "_refresh_question_list", "_on_question_select",
    "_on_session_select", "_build_performance_table", "_render_result_to_panel",
    "_show_pareto_report", "_show_cognitive_efficiency", "_show_saturation_status",
    "_show_failure_patterns", "_show_dual_loop_report", "_show_skill_status",
    "_show_wisdom_commons", "_show_rumad_status", "_show_exploration_status",
    "_show_inspiration_furnace", "_show_gödel_status",
}

GUI_SERVICE_MAP = {
    "_load_session_list": "session",
    "_restore_original_sessions": "session",
    "_do_chat": "chat",
    "_chat_done": "chat",
    "_handle_title_generation_after_reply": "chat",
    "_generate_dual_titles": "chat",
    "_generate_round_label_simple": "chat",
    "_do_file_chat": "chat",
    "_file_chat_done": "chat",
    "_build_session_context": "chat",
    "_do_deep_reasoning": "chat",
    "_single_deep_reasoning": "chat",
    "_debate_engine_reasoning": "chat",
    "_is_complex_question": "chat",
    "_get_debate_rounds": "chat",
    "_sync_debate_round_state": "chat",
    "_do_crystal": "crystal",
    "_crystal_done": "crystal",
    "_existing_crystal_ids": "crystal",
    "_shorten_crystal_content": "crystal",
    "_build_crystallization_prompt": "crystal",
    "_normalize_crystal_response": "crystal",
    "_find_similar_crystals": "crystal",
    "_format_crystal_update_preview": "crystal",
    "_commit_crystal_update": "crystal",
    "_do_force_archive": "crystal",
    "_append_pending_card": "crystal",
    "_update_files": "crystal",
    "_update_skill_content": "skill",
    "_append_audit_report": "crystal",
    "_extract_pending_content": "crystal",
    "_confirm_pending_card": "crystal",
    "_confirm_pending_card_with_content": "crystal",
    "_read_edit_and_commit_pending": "crystal",
    "_create_pending_from_competition": "crystal",
    "_do_contribute_crystal": "wisdom",
    "_contribute_done": "wisdom",
    "_do_inherit_seeds": "wisdom",
    "_inherit_done": "wisdom",
    "_load_task_cards": "crystal",
    "_save_task_cards": "crystal",
    "_do_migrate_to_skills": "skill",
    "_do_validate_skills": "skill",
    "_export_all_skills": "skill",
    "_export_skill_dialog": "skill",
    "_search_duckduckgo": "search",
    "_do_meta_search": "search",
    "_sync_vector_store": "search",
    "_do_external_fetch": "search",
    "_external_fetch_done": "search",
    "_start_batch": "batch",
    "_stop_batch_process": "batch",
    "_batch_done": "batch",
    "_ask_daily_keywords": "planner",
    "_run_daily_plan_thread": "planner",
    "_stop_daily_plan": "planner",
    "_check_and_run_daily_plan": "planner",
    "_manual_run_daily_plan": "planner",
    "_do_gödel_evolution": "evolution",
    "_gödel_evolution_done": "evolution",
    "_do_recursive_evolution": "evolution",
    "_recursive_evolution_done": "evolution",
    "_do_force_self_healing": "evolution",
    "_do_force_exploration": "evolution",
    "_force_exploration_done": "evolution",
    "_do_inspiration_phase2": "evolution",
    "_inspiration_phase2_done": "evolution",
    "_polish_report": "report",
    "_output_debate_report": "report",
    "_save_report_to_desktop": "report",
    "_build_performance_table": "report",
    "_generate_elegant_narrative": "report",
    "_stream_elegant_with_typewriter": "report",
    "_do_auto_health_fix": "health",
    "_do_anti_fraud_audit": "health",
    "_anti_fraud_audit_done": "health",
    "_on_session_select": "session",
    "_refresh_question_list": "session",
    "_on_question_select": "session",
    "_extract_keywords": "crystal",
    "_load_roles": "governance",
    "_get_current_profile": "governance",
    "_export_agents_md": "governance",
    "_init_app": "system",
    "_load_api_from_env": "governance",
    "_toggle_rumad": "evolution",
    "_vote": "crystal",
    "_open_twin_workbench": "twin",
    "_show_deposit_popup": "crystal",
    "_show_role_vote_popup": "crystal",
    "_preview_crystal_update": "crystal",
    "_render_result_to_panel": "report",
    "_show_pareto_report": "evolution",
    "_show_cognitive_efficiency": "system",
    "_show_saturation_status": "evolution",
    "_show_failure_patterns": "evolution",
    "_show_dual_loop_report": "evolution",
    "_show_skill_status": "skill",
    "_show_wisdom_commons": "wisdom",
    "_show_rumad_status": "evolution",
    "_show_exploration_status": "evolution",
    "_show_inspiration_furnace": "evolution",
    "_show_gödel_status": "evolution",
}

WEB_SERVICE_MAP = {
    "check_ai_access": "auth",
    "_user_effective_key": "auth",
    "startup_event": "system",
    "auth_middleware": "auth",
    "sync_vector_store": "search",
    "create_checkout_session": "payment",
    "payment_webhook": "payment",
    "get_trending": "search",
    "refresh_trending": "search",
    "get_radar": "search",
    "vector_status": "search",
    "get_conflicts": "search",
    "register": "auth",
    "login": "auth",
    "me": "auth",
    "update_api_key": "auth",
    "delete_api_key": "auth",
    "delete_account": "auth",
    "privacy": "system",
    "list_skills": "skill",
    "get_skill": "skill",
    "validate_skills": "skill",
    "validate_single_skill": "skill",
    "migrate_to_skills": "skill",
    "_job": "batch",
    "_set_job": "batch",
    "_log_job": "batch",
    "_run_job": "batch",
    "_sessions": "session",
    "_ensure_session": "session",
    "_add_message": "session",
    "_history_context": "session",
    "_questions": "session",
    "_shorten": "crystal",
    "_existing_crystal_ids": "crystal",
    "_extract_keywords": "crystal",
    "_build_crystallization_prompt": "crystal",
    "_normalize_crystal_response": "crystal",
    "_similar": "crystal",
    "_append_pending_card": "crystal",
    "_update_files": "crystal",
    "_assets": "crystal",
    "_pending_cards": "crystal",
    "_task_cards": "crystal",
    "_save_task_cards": "crystal",
    "_load_roles": "governance",
    "backend_status": "system",
    "backend_login": "system",
    "backend_logout": "system",
    "list_sessions": "session",
    "create_session": "session",
    "get_session": "session",
    "rename_session": "session",
    "delete_session": "session",
    "clear_session": "session",
    "chat": "chat",
    "crystallize": "crystal",
    "commit_crystallize": "crystal",
    "deep_reasoning": "chat",
    "file_chat": "chat",
    "start_batch": "batch",
    "stop_batch": "batch",
    "get_job": "batch",
    "assets": "crystal",
    "get_fingerprint": "crystal",
    "submit_hebbian_reward": "crystal",
    "get_hebbian_stats_endpoint": "crystal",
    "patch_asset": "crystal",
    "delete_asset": "crystal",
    "pending": "crystal",
    "confirm_pending": "crystal",
    "ignore_pending": "crystal",
    "tasks": "crystal",
    "resolve_task": "crystal",
    "ignore_task": "crystal",
    "status": "system",
    "holes": "crystal",
    "today": "system",
    "health": "health",
    "health_dashboard": "health",
    "search": "search",
    "daily_plan": "planner",
    "stop_daily_plan": "planner",
}

WEB_UI = {"index", "bootstrap", "favicon_ico"}


def method_items(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CrystalTreeApp":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef):
                    yield fn


def function_items(tree: ast.AST):
    for fn in tree.body:
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield fn


def line_count(node: ast.AST) -> int:
    return node.end_lineno - node.lineno + 1


def analyze_gui() -> list:
    tree = ast.parse((ROOT / "access" / "gui.py").read_text(encoding="utf-8"))
    items = []
    for fn in method_items(tree):
        name = fn.name
        if name in GUI_SERVICE:
            cat = CAT_SERVICE
        elif name in GUI_MIXED:
            cat = CAT_MIXED
        else:
            cat = CAT_UI
        service = GUI_SERVICE_MAP.get(name, "待定")
        items.append(
            {
                "file": "access/gui.py",
                "name": name,
                "start": fn.lineno,
                "end": fn.end_lineno,
                "lines": line_count(fn),
                "category": cat,
                "service": service,
            }
        )
    return items


def analyze_web() -> list:
    tree = ast.parse((ROOT / "access" / "web.py").read_text(encoding="utf-8"))
    items = []
    for fn in function_items(tree):
        name = fn.name
        if name in WEB_UI:
            cat = CAT_UI
        else:
            cat = CAT_SERVICE
        service = WEB_SERVICE_MAP.get(name, "待定")
        items.append(
            {
                "file": "access/web.py",
                "name": name,
                "start": fn.lineno,
                "end": fn.end_lineno,
                "lines": line_count(fn),
                "category": cat,
                "service": service,
            }
        )
    return items


def summarize(items: list) -> dict:
    by_file = defaultdict(lambda: defaultdict(int))
    by_service = defaultdict(int)
    for item in items:
        by_file[item["file"]][item["category"]] += item["lines"]
        by_file[item["file"]]["total"] += item["lines"]
        if item["category"] != CAT_UI:
            by_service[item["service"]] += item["lines"]
    return {
        "items": items,
        "by_file": dict(by_file),
        "by_service": dict(sorted(by_service.items(), key=lambda kv: -kv[1])),
    }


def to_markdown(data: dict) -> str:
    today = date.today().isoformat()
    lines = [
        "# access 层迁移盘点",
        "",
        f"- 生成日期：{today}",
        "- 说明：只读分析，未修改任何现有代码；“混合”表示界面与业务需要拆分。",
        "",
        "## 总览",
        "",
        "| 文件 | 界面壳 | 业务逻辑 | 混合 | 合计（函数体） |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for file_name, stats in data["by_file"].items():
        lines.append(
            f"| {file_name} | {stats.get(CAT_UI, 0)} | "
            f"{stats.get(CAT_SERVICE, 0)} | {stats.get(CAT_MIXED, 0)} | {stats['total']} |"
        )
    lines.extend(["", "## 按最终归属服务", "", "| 归属 | 预计搬迁行数 |", "| --- | ---: |"])
    for service, count in data["by_service"].items():
        lines.append(f"| {service} | {count} |")
    lines.extend(["", "## 明细", "", "| 文件 | 函数 | 起止行 | 行数 | 类型 | 归属 |", "| --- | --- | --- | ---: | --- | --- |"])
    for item in data["items"]:
        lines.append(
            f"| {item['file']} | {item['name']} | {item['start']}-{item['end']} | "
            f"{item['lines']} | {item['category']} | {item['service']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    items = analyze_gui() + analyze_web()
    data = summarize(items)
    report_md = ROOT / "docs" / f"migration_inventory_{date.today().strftime('%Y%m%d')}.md"
    report_json = report_md.with_suffix(".json")
    report_md.write_text(to_markdown(data), encoding="utf-8")
    report_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(
        {
            "by_file": data["by_file"],
            "by_service": data["by_service"],
            "report_md": str(report_md),
            "report_json": str(report_json),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
