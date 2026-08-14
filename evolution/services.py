"""??????"""

from __future__ import annotations

from typing import Any

from evolution.meta_search import MetaSearchEngine


def run_godel_evolution(
    engine: Any,
    role: str,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        result = engine.meta.trigger_gödel_evolution(role)
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()

def run_recursive_evolution(
    engine: Any,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        agent = engine.meta.gödel_agent
        result = agent.run_recursive_evolution_cycle()
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()

def run_anti_fraud_audit(
    engine: Any,
    dialogue: str,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        context = {
            "dialogue": dialogue,
            "ip": "",
            "text_zh": "你好，我是认知晶体树的用户，我想了解更多关于AI的知识。",
            "text_en": (
                "Hello, I am a user of Cognitive Crystal Tree, "
                "I want to learn more about AI."
            ),
        }
        result = engine.meta.run_anti_fraud_audit(context)
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()

def run_force_exploration(
    engine: Any,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        explorer = engine.meta.force_explorer
        result = explorer.run_scheduled_exploration()
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()

def run_inspiration_phase2(
    engine: Any,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        result = engine.inspiration_furnace_review_phase2()
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()

def run_meta_search(
    engine: Any,
    ai: Any,
    user_input: str,
    on_output: Any,
    on_log: Any,
    on_done: Any,
) -> None:
    """执行 Meta 搜索并生成对比结果文本。"""
    try:
        meta_engine = MetaSearchEngine(engine, ai)
        result = meta_engine.run_comparison(user_input)
        if "error" in result:
            on_log(f"❌ Meta搜索失败：{result['error']}", "error")
            return
        lines = ["🔍 认知路径平行对比结果", "=" * 40, ""]
        for i, scored_path in enumerate(result.get("paths", []), 1):
            path = scored_path.get("path", {})
            score = scored_path.get("score", 0)
            details = scored_path.get("details", {})
            lines.append(f"【路径{i}】{path.get('name', '未命名')} - 得分: {score}")
            lines.append(f"  策略: {path.get('strategy', 'unknown')}")
            lines.append(f"  晶体: {', '.join(path.get('crystal_ids', [])[:5])}")
            lines.append(
                f"  详情: 晶体数={details.get('crystal_count_score', 0)}, "
                f"指纹匹配={details.get('fingerprint_score', 0)}"
            )
            lines.append("")
        best = result.get("best_path")
        if best:
            path = best.get("path", {})
            lines.append(f"🏆 最优路径: {path.get('name', '未命名')}")
            lines.append(f"  推荐晶体: {', '.join(path.get('crystal_ids', [])[:5])}")
            lines.append(f"  得分: {best.get('score', 0)}")
        on_output("\n".join(lines))
    except Exception as e:
        on_log(f"❌ Meta搜索出错：{e}", "error")
    on_done()

def force_self_healing(
    engine: Any,
    ai: Any,
    on_log: Any,
) -> None:
    """初始化并强制触发自我修复。"""
    if not engine.self_healer:
        on_log("⚠️ 自我修复未初始化，正在启动...", "warning")
        engine.start_self_healing(ai)
        if not engine.self_healer:
            on_log("❌ 自我修复初始化失败", "error")
            return
    on_log("🔧 强制触发自我修复（测试模式）...", "system")
    try:
        engine.self_healer.force_trigger_repair()
        on_log("✅ 自我修复已触发，请查看日志", "success")
    except Exception as e:
        on_log(f"❌ 强制触发失败: {e}", "error")
