#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a complete architecture diagram (TXT) from the v5 source tree."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = Path(r"C:\Users\Administrator\Desktop\系统架构图v5_完整版.txt")

DEFAULT_MARK = "✅ 已实现"
SPECIAL_MARK = {
    "harness/alarm.py": "✅ 八道防线（8道：知识/偏见/固化/枯竭/证据/逻辑/过度推断/可靠性）",
    "harness/orchestrator.py": "🔶 五版输出已实现，压缩版硬契约待接入",
    "harness/reporting.py": "✅ 压缩版硬契约已实现（字数/结构校验/重试/规则降级）",
    "harness/rumad.py": "✅ 多奖励闭环（采纳/驳回/质量/复用/多说话/票选）+ 时间衰减",
    "harness/engine.py": "✅ 已实现（含双环验证/Hebbian检索加权/突触管理）",
    "evolution/godel.py": "✅ Gödel三层进化+递归闭环已实现",
    "evolution/meta_layer.py": "✅ 元层/原语/灵感熔炉/反诈审计已实现",
    "evolution/fast_loop.py": "✅ 已接入双环快环筛选",
    "evolution/slow_loop.py": "✅ 已接入双环慢环判定/回滚",
    "evolution/staging_pool.py": "✅ 已接入双环暂存池",
    "evolution/operators.py": "✅ 可执行算子（prune/promote/merge/graft + 回滚）",
    "evolution/governance.py": "🔶 原型：提案/辩论/审计为模拟实现",
    "access/gui.py": "✅ 已实现（会话/辩论/进化/市场功能入口）",
    "access/web.py": "✅ 已实现（FastAPI全套API）",
}


def py_defs(path: Path):
    """Extract classes, methods and module-level functions via AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    items = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            items.append((node.lineno, "fn", node.name, _nested_names(node)))
        elif isinstance(node, ast.ClassDef):
            items.append((node.lineno, "class", node.name, []))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    items.append((sub.lineno, "method", sub.name, _nested_names(sub)))
    items.sort(key=lambda x: x[0])
    return items


def _nested_names(node):
    """Collect function names defined inside a function (closures/local helpers)."""
    names = []
    for child in node.body:
        for n in ast.walk(child):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(n.name)
    return names


def render_py(path: Path, prefix: str, last: bool = False):
    rel = path.relative_to(ROOT).as_posix()
    mark = SPECIAL_MARK.get(rel, DEFAULT_MARK)
    arrow = "└── " if last else "├── "
    lines.append(f"{prefix}{arrow}{path.name}  # {mark}")
    child = prefix + ("    " if last else "│   ")
    defs = py_defs(path)
    for i, (_, kind, name, inner) in enumerate(defs):
        arrow = "└── " if i == len(defs) - 1 else "├── "
        if kind == "class":
            lines.append(f"{child}{arrow}{name} (class)")
        elif kind == "method":
            lines.append(f"{child}│   {arrow}def {name}(...)")
            for j, inner_name in enumerate(inner):
                inner_arrow = "└── " if j == len(inner) - 1 else "├── "
                lines.append(f"{child}│   │   {inner_arrow}def {inner_name}(...)  # 嵌套函数")
        else:
            lines.append(f"{child}{arrow}def {name}(...)")
            for j, inner_name in enumerate(inner):
                inner_arrow = "└── " if j == len(inner) - 1 else "├── "
                lines.append(f"{child}│   {inner_arrow}def {inner_name}(...)  # 嵌套函数")


def render_js_functions(path: Path, prefix: str):
    text = path.read_text(encoding="utf-8", errors="replace")
    names = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", text))
    names |= set(re.findall(r"const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(", text))
    names |= set(re.findall(r"async\s+function\s+([A-Za-z_$][\w$]*)\s*\(", text))
    lines.append(f"{prefix}├── {path.name}  # ✅ 前端页面")
    child = prefix + "│   "
    for i, name in enumerate(sorted(names)):
        arrow = "└── " if i == len(names) - 1 else "├── "
        lines.append(f"{child}{arrow}function {name}(...)")


def render_dir(dir_name: str, comment: str, files: list, prefix: str):
    lines.append(f"{prefix}├── {dir_name}/  # {comment}")
    child = prefix + "│   "
    init = ROOT / dir_name / "__init__.py"
    items = ([init] if init.exists() else []) + files
    for i, f in enumerate(items):
        last = i == len(items) - 1
        sub = prefix + "    " if last else child
        render_py(f, sub)


lines = []
lines.append("认知晶体树 v5 · 可插拔自进化 · 完整系统架构")
lines.append("Project Root/  # D:\\AI开发软件\\卢总\\认知晶体树\\认知晶体树5_可插拔自进化")
lines.append("│")

# ---------- root files ----------
root_files = [ROOT / "main.py"]
for i, f in enumerate(root_files):
    render_py(f, "", last=(i == len(root_files) - 1))
for name in ["README.md", "requirements.txt", "requirements-server.txt", ".env", "security.key",
             "启动GUI.bat", "启动Web.bat"]:
    lines.append(f"├── {name}  # ✅ 项目文件/启动脚本")

# ---------- access ----------
render_dir("access", "🚪 接入层（GUI / Web / CLI）", [
    ROOT / "access" / "cli.py",
    ROOT / "access" / "gui.py",
    ROOT / "access" / "web.py",
], "")
lines.append("│   ├── mobile_api.py  # ⬜ 待实现：移动端/GraphQL轻量接口")

# ---------- addons ----------
render_dir("addons", "🧩 市场模块（addon SDK + 作文模块骨架）", [
    ROOT / "addons" / "base.py",
    ROOT / "addons" / "composition" / "__init__.py",
    ROOT / "addons" / "composition" / "config.py",
    ROOT / "addons" / "composition" / "prompts.py",
    ROOT / "addons" / "composition" / "hooks.py",
    ROOT / "addons" / "composition" / "market.py",
], "")

# ---------- core ----------
render_dir("core", "🧱 基石层（契约/模型/持久化/指纹）", [
    ROOT / "core" / "interfaces.py",
    ROOT / "core" / "models.py",
    ROOT / "core" / "persistence.py",
    ROOT / "core" / "registry.py",
    ROOT / "core" / "fingerprint.py",
    ROOT / "core" / "benchmarks.py",
    ROOT / "core" / "dependencies.py",
], "")

# ---------- data ----------
render_dir("data", "💾 数据访问层", [
    ROOT / "data" / "storage.py",
    ROOT / "data" / "vector_store.py",
], "")

# ---------- evolution ----------
render_dir("evolution", "🧬 变异进化层（自进化）", [
    ROOT / "evolution" / "godel.py",
    ROOT / "evolution" / "meta_layer.py",
    ROOT / "evolution" / "fast_loop.py",
    ROOT / "evolution" / "slow_loop.py",
    ROOT / "evolution" / "staging_pool.py",
    ROOT / "evolution" / "operators.py",
    ROOT / "evolution" / "governance.py",
], "")

# ---------- external ----------
render_dir("external", "📡 外部世界接口", [
    ROOT / "external" / "ai_client.py",
    ROOT / "external" / "fetcher.py",
    ROOT / "external" / "network.py",
    ROOT / "external" / "search.py",
], "")
lines.append("│   ├── intake_manager.py  # ⬜ 待实现：原始摄入库管理器")

# ---------- governance ----------
render_dir("governance", "⚙️ 配置治理层", [
    ROOT / "governance" / "config.py",
    ROOT / "governance" / "prompt_templates.py",
], "")
for yaml in ["evolution_policy.yaml", "harness_flows.yaml", "license.yaml"]:
    lines.append(f"│   ├── config/{yaml}  # ✅ 配置")

# ---------- harness ----------
render_dir("harness", "🐎 实时驾驭层（大脑）", [
    ROOT / "harness" / "engine.py",
    ROOT / "harness" / "orchestrator.py",
    ROOT / "harness" / "rumad.py",
    ROOT / "harness" / "gate.py",
    ROOT / "harness" / "alarm.py",
    ROOT / "harness" / "audit.py",
    ROOT / "harness" / "contemplative.py",
    ROOT / "harness" / "force_explorer.py",
    ROOT / "harness" / "reporting.py",
    ROOT / "harness" / "runner.py",
    ROOT / "harness" / "twin_workbench.py",
], "")
processor_files = [
    ROOT / "harness" / "processors" / "__init__.py",
    ROOT / "harness" / "processors" / "debate.py",
    ROOT / "harness" / "processors" / "planner.py",
    ROOT / "harness" / "processors" / "batch_processor.py",
    ROOT / "harness" / "processors" / "dag_demo.py",
]
lines.append("│   └── processors/  # 🔧 处理器注册与执行")
for i, f in enumerate(processor_files):
    render_py(f, "│       ", last=(i == len(processor_files) - 1))

# ---------- cycle (placeholder) ----------
lines.append("├── cycle/  # 🔄 双环控制论模型（规划中）")
lines.append("│   ├── inner_loop.py  # 🔶 内环：辩论→收敛→输出（由 harness 驱动）")
lines.append("│   ├── outer_loop.py  # 🔶 外环：感知→孔洞→觅食→压力测试→修剪")
lines.append("│   └── connector.py  # 🔶 内外环桥接（晶体代谢接口）")

# ---------- tools ----------
render_dir("tools", "🔧 CLI/迁移/审计工具集", sorted(
    [p for p in (ROOT / "tools").glob("*.py") if p.name != "generate_architecture_txt.py"],
    key=lambda p: p.name,
), "")

# ---------- tests ----------
render_dir("tests", "🧪 回归测试（97项）", sorted(
    [p for p in (ROOT / "tests").glob("*.py")],
    key=lambda p: p.name,
), "")

# ---------- web_static ----------
lines.append("├── web_static/  # 🌐 前端静态资源")
render_js_functions(ROOT / "web_static" / "index.html", "│   ")
for f in ["styles.css", "app.js", "cognitive-map.html", "wechat_qr.png", "robot-workshop-pattern.svg",
          "index - 副本.html", "app - 副本.js", "styles - 副本.css"]:
    lines.append(f"│   ├── {f}  # ✅ 静态文件")

# ---------- runtime data ----------
lines.append("├── 晶体树文件夹/  # 💾 运行时数据根（兼容2.2）")
lines.append("│   ├── chat_sessions.db  # ✅ 会话库")
lines.append("│   ├── 晶体数据/  # ✅ 晶体卡片/孔洞分层/备份")
lines.append("│   ├── 晶体数据 - 副本/  # ✅ 历史晶体备份")
lines.append("│   ├── 核心配置/  # ✅ 角色定义/原则/模板")
lines.append("│   ├── 系统日志/  # ✅ 用户/突触/Hebbian/审计/报告")
lines.append("│   ├── 暂存区/  # ✅ 待确认卡片")
lines.append("│   ├── skills/  # ✅ Skill 目录")
lines.append("│   └── model_cache/  # ✅ 向量模型缓存")

# ---------- github (placeholder) ----------
lines.append("├── .github/  # ⬜ GitHub生态集成（CI已具备，cognitive-tree未建）")
lines.append("│   └── cognitive-tree/  # ⬜ rules/skills/prompts/README")

lines.append("└── docs/  # ✅ 文档（隐私说明/上线前验证等）")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("WROTE", OUT)
print("LINES", len(lines))
