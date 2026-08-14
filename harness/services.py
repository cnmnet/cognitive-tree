"""Harness 服务：系统状态、健康、指纹、Hebbian、资产与归档能力。"""

from __future__ import annotations

import re
import hashlib
import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from data.services import add_session_message
from external.ai_client import fallback_session_title
from core.scoring import score_line, score_payload
from governance.config import Config
from harness.processors.debate import DebateEngine
from harness.processors.planner import DailyPlanner
from harness.reporting import (
    COMPRESSED_REPORT_TARGET,
    QUICK_VIEW_TARGET,
    build_debate_report_markdown,
    build_quick_view_report,
    ensure_performance_board,
    polish_report_markdown,
)
from harness.twin_workbench import TwinWorkbench
from core.text_utils import normalize_text


def existing_crystal_ids(files: Any) -> set:
    """从晶体文件读取已有 C 编号。"""
    return set(re.findall(r"\bC\d+\b", files.read("crystals")))


def similar_crystals(engine: Any, content: str, threshold: float = 0.55) -> List[Dict[str, Any]]:
    """返回与内容相似的晶体。"""
    matches = []
    for crystal in engine.parse_crystals():
        score = engine._simple_similarity(content, crystal.content)
        if score >= threshold:
            matches.append(
                {
                    "score": round(score, 2),
                    "id": crystal.id,
                    "content": crystal.content[:80],
                }
            )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:5]


def similar_crystal_pairs(engine: Any, content: str, threshold: float = 0.55) -> List[tuple]:
    """返回与内容相似的晶体对（score, crystal），供预览格式化使用。"""
    matches = []
    for crystal in engine.parse_crystals():
        score = engine._simple_similarity(content, crystal.content)
        if score >= threshold:
            matches.append((round(score, 2), crystal))
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[:5]


def simple_keywords(text: str) -> List[str]:
    """本地简单关键词提取（晶体化快速模式兜底）。"""
    words = re.findall(r'[\w\u4e00-\u9fff]+', text)
    stop = {"的", "了", "和", "与", "或", "一个", "这个", "那个", "如何", "什么", "为什么"}
    kw = [w for w in words if w not in stop][:5]
    return kw if kw else ["晶体树", "认知"]


def parse_keyword_input(text: str) -> List[str]:
    """把用户输入的每日计划关键词拆分为列表。"""
    if text is None:
        return []
    return [item.strip() for item in re.split(r"[,，;；\s\n]+", text) if item.strip()]


def run_gui_daily_plan(
    engine: Any,
    ai: Any,
    fetcher: Any,
    log: Any,
    update_status: Any,
    keywords: List[str],
    time_budget_seconds: int,
    stop_flag: Any,
    progress: Any,
    on_done: Any,
) -> None:
    planner = DailyPlanner(engine, ai, fetcher, log, update_status)
    try:
        planner.run(
            intent_keywords=keywords,
            time_budget_seconds=time_budget_seconds,
            stop_flag=stop_flag,
            progress_callback=progress,
        )
    finally:
        on_done()


def build_crystallization_prompt(
    engine: Any,
    config: Any,
    existing_ids: set,
    user_input: str,
    search_res: str,
    l0_holes: Any = None,
    l1_crystals: Any = None,
    include_constraints: bool = False,
) -> str:
    """生成晶体化 Prompt。"""
    if l0_holes is None or l1_crystals is None:
        l0_holes, l1_crystals = engine.get_attention_context()
    l0_text = "\n".join([f"- {h.id}: {h.content[:100]}" for h in l0_holes])
    l1_text = "\n".join(
        [
            f"- {c.id}: {c.content[:80]} | links={','.join(c.links)}"
            for c in l1_crystals[: config.L1_MAX]
        ]
    )
    related = engine.get_associative_crystals(user_input, top_k=8)
    related_text = "\n".join(
        [f"- {c.id}: {c.content[:80]} | links={','.join(c.links)}" for c in related]
    )
    existing = ", ".join(sorted(existing_ids)[-20:])
    prompt = f"""
你是认知晶体树的结构化整理器。请只返回 JSON，不要返回 Markdown、解释或代码块。

目标：
1. 从用户输入中提炼可长期复用的认知晶体。
2. 优先连接已有晶体，不要重复制造同义晶体。
3. 暴露冲突和孔洞，但不要夸大不确定性。
4. 每条晶体 content 必须不超过 80 个中文字符。

用户输入：
{user_input}

外部搜索结果：
{search_res}

L0 核心孔洞：
{l0_text}

L1 注意力晶体：
{l1_text}

联想检索命中的相关晶体：
{related_text}

近期已有晶体 ID：
{existing}

返回 JSON schema：
{{
  "new_crystals": [
    {{"id": "", "content": "不超过80字的新晶体", "links": ["C001"]}}
  ],
  "updated_crystals": [
    {{"id": "C001", "new_content": "不超过80字的更新后内容"}}
  ],
  "new_holes": [
    {{"id": "", "content": "需要继续验证的问题", "urgency": 0.5, "layer": 2}}
  ],
  "updated_holes": [
    {{"id": "H001", "content": "更新后孔洞内容"}}
  ],
  "conflicts": [
    {{"a": "C001", "b": "C002", "reason": "冲突原因"}}
  ],
  "report_summary": "一句话总结本次结构变化",
  "pending_cards": [
    {{"type": "晶体候选", "content": "待确认内容", "source": "AI生成", "confidence": "中"}}
  ]
}}
"""
    if include_constraints:
        prompt += """
约束：
- 如果只是表达、例子或临时信息，不要直接入库，放入 pending_cards。
- new_crystals 的 id 可以留空，系统会自动分配。
- links 只能引用已存在或本次返回的新晶体 ID；不确定就留空数组。
- 没有内容的字段返回空数组。
"""
    return prompt


def normalize_crystal_response(
    files: Any,
    engine: Any,
    existing_ids: set,
    ai_response: Dict[str, Any],
    include_similar: bool = False,
) -> Dict[str, Any]:
    """把 AI 返回的晶体化结果标准化。"""
    if not isinstance(ai_response, dict):
        return {"error": "AI返回不是JSON对象"}

    next_num = (
        max(
            [int(i) for i in re.findall(r"C(\d+)", files.read("crystals"))],
            default=0,
        )
        + 1
    )
    seen_contents = {normalize_text(c.content) for c in engine.parse_crystals()}
    id_map: Dict[str, str] = {}
    normalized_new = []
    for item in ai_response.get("new_crystals", []) or []:
        content = normalize_text(item.get("content", ""))
        if not content or content in seen_contents:
            continue
        old_id = str(item.get("id", "")).strip()
        new_id = f"C{next_num:03d}"
        next_num += 1
        if old_id and old_id not in existing_ids:
            id_map[old_id] = new_id
        links = []
        for link in item.get("links", []) or []:
            link = id_map.get(str(link).strip(), str(link).strip())
            if re.fullmatch(r"C\d+", link) and (
                link in existing_ids or link in id_map.values()
            ):
                links.append(link)
        normalized_item = {
            "id": new_id,
            "content": content,
            "links": sorted(set(links)),
        }
        if include_similar:
            normalized_item["similar"] = similar_crystals(engine, content)
        normalized_new.append(normalized_item)
        seen_contents.add(content)

    valid_ids = existing_ids | {c["id"] for c in normalized_new}
    normalized_updates = []
    for item in ai_response.get("updated_crystals", []) or []:
        cid = str(item.get("id", "")).strip()
        content = normalize_text(item.get("new_content") or item.get("content", ""))
        if cid in existing_ids and content:
            normalized_updates.append({"id": cid, "new_content": content})

    normalized_holes = []
    next_hole = (
        max(
            [int(i) for i in re.findall(r"H(\d+)", files.read("holes"))],
            default=0,
        )
        + 1
    )
    for item in ai_response.get("new_holes", []) or []:
        content = normalize_text(item.get("content", ""), 120)
        if not content:
            continue
        try:
            urgency = max(0.0, min(1.0, float(item.get("urgency", 0.5))))
        except (TypeError, ValueError):
            urgency = 0.5
        try:
            layer = min(3, max(1, int(item.get("layer", 2))))
        except (TypeError, ValueError):
            layer = 2
        normalized_holes.append(
            {
                "id": f"H{next_hole:03d}",
                "content": content,
                "urgency": urgency,
                "layer": layer,
            }
        )
        next_hole += 1

    normalized_conflicts = []
    for item in ai_response.get("conflicts", []) or []:
        a = str(item.get("a") or item.get("crystal_a") or "").strip()
        b = str(item.get("b") or item.get("crystal_b") or "").strip()
        if a in valid_ids and b in valid_ids and a != b:
            normalized_conflicts.append(
                {
                    "a": a,
                    "b": b,
                    "reason": str(item.get("reason", ""))[:120],
                }
            )

    normalized_pending = []
    for item in ai_response.get("pending_cards", []) or []:
        content = normalize_text(item.get("content", ""), 200)
        if content:
            normalized_pending.append(
                {
                    "type": str(item.get("type", "晶体候选")),
                    "content": content,
                    "source": str(item.get("source", "AI生成")),
                    "confidence": str(item.get("confidence", "中")),
                }
            )

    return {
        "new_crystals": normalized_new,
        "updated_crystals": normalized_updates,
        "new_holes": normalized_holes,
        "updated_holes": ai_response.get("updated_holes", []) or [],
        "conflicts": normalized_conflicts,
        "report_summary": str(ai_response.get("report_summary", "晶体化完成"))[:120],
        "pending_cards": normalized_pending,
    }


def append_pending_card(files: Any, card: Dict[str, Any]) -> bool:
    """追加一条待确认卡片，内容重复时不追加。"""
    content = normalize_text(card.get("content", ""), 200)
    if not content:
        return False
    pending = files.read("pending")
    if content in pending:
        return False
    suffix = int(hashlib.sha256(content.encode("utf-8")).hexdigest(), 16) % 1000
    card_id = f"PENDING-{datetime.now().strftime('%Y%m%d%H%M%S')}-{suffix:03d}"
    block = f"""
## {card_id}
- 类型：{card.get('type', '晶体候选')}
- 来源：{card.get('source', 'AI生成')}
- 置信度：{card.get('confidence', '中')}
- 内容：{content}
- AI判断：建议人工确认后再转为晶体。
"""
    files.append("pending", "\n" + block + "\n")
    return True


def assets(engine: Any) -> Dict[str, Any]:
    """读取当前晶体与孔洞快照。"""
    l1, l2, l3 = engine.update_crystal_layers()
    state = engine.load_layer_state()
    layers = state.get("layers", {})
    heat = state.get("heat_map", {})
    last = state.get("last_accessed", {})
    manual = state.get("manual_override", {})
    crystals = []
    for c in engine.parse_crystals():
        crystals.append(
            {
                "id": c.id,
                "content": c.content,
                "links": c.links,
                "layer": layers.get(c.id, "L2"),
                "heat": round(float(heat.get(c.id, 0.0)), 2),
                "last_accessed": last.get(c.id, "从未"),
                "fixed": manual.get(c.id) == "L1_fixed",
            }
        )
    holes = [
        {"id": h.id, "content": h.content, "urgency": h.urgency, "layer": h.layer}
        for h in engine.parse_holes()
    ]
    return {
        "crystals": crystals,
        "holes": holes,
        "counts": {
            "L1": len(l1),
            "L2": len(l2),
            "L3": len(l3),
            "total": len(crystals),
        },
    }


def holes_snapshot(files: Any, engine: Any) -> Dict[str, Any]:
    return {"content": files.read("holes"), "holes": assets(engine)["holes"]}


def today_snapshot(files: Any) -> Dict[str, Any]:
    today_text = datetime.now().strftime("%Y-%m-%d")
    compact = datetime.now().strftime("%Y%m%d")
    change_log = files.read("change_log")
    sections = re.findall(
        rf"(## {re.escape(today_text)}.*?)(?=\n## \d{{4}}-\d{{2}}-\d{{2}}|\Z)",
        change_log,
        re.DOTALL,
    )
    pending = [
        c for c in pending_cards(files) if c["id"].startswith(f"PENDING-{compact}")
    ]
    tasks = [
        t
        for t in task_cards(files)
        if str(t.get("id", "")).startswith(f"TASK-{compact}")
    ]
    return {"date": today_text, "changes": sections, "pending": pending, "tasks": tasks}


def pending_cards(files: Any) -> List[Dict[str, Any]]:
    """解析待确认卡片 Markdown。"""
    content = files.read("pending")
    cards = []
    for cid, body in re.findall(
        r"## (PENDING-\d+-\d+)\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    ):
        item = {
            "id": cid,
            "type": "",
            "title": "",
            "source": "",
            "content": "",
            "raw": body.strip(),
        }
        for line in body.splitlines():
            if line.startswith("- 类型："):
                item["type"] = line.split("：", 1)[1].strip()
            elif line.startswith("- 标题："):
                item["title"] = line.split("：", 1)[1].strip()
            elif line.startswith("- 来源："):
                item["source"] = line.split("：", 1)[1].strip()
            elif (
                line.startswith("- 内容摘要：")
                or line.startswith("- 内容：")
                or line.startswith("- 生成晶体候选：")
            ):
                item["content"] = line.split("：", 1)[1].strip()
        if not item["title"]:
            item["title"] = item["content"][:50] or cid
        cards.append(item)
    return cards


def task_cards(files: Any) -> List[Dict[str, Any]]:
    """读取任务卡片 JSON。"""
    if not files.exists("task_cards"):
        return []
    try:
        return json.loads(files.read("task_cards") or "[]")
    except json.JSONDecodeError:
        return []


def save_task_cards(files: Any, cards: List[Dict[str, Any]]) -> None:
    """保存任务卡片 JSON。"""
    files.write("task_cards", json.dumps(cards, ensure_ascii=False, indent=2))


def confirm_pending_card(
    files: Any,
    engine: Any,
    card_id: str,
    content: str,
    force: bool = False,
) -> Dict[str, Any]:
    """确认待确认卡片，存在相似晶体且未强制时要求二次确认。"""
    pending_content = files.read("pending")
    match = re.search(
        rf"(##\s*{re.escape(card_id)}.*?)(?=\n## |\Z)",
        pending_content,
        re.DOTALL,
    )
    if not match:
        raise ValueError("卡片不存在")
    content = normalize_text(content)
    if not content:
        raise ValueError("内容为空")
    similar = similar_crystals(engine, content)
    if similar and not force:
        return {"ok": False, "needs_force": True, "similar": similar}
    crystals = files.read("crystals")
    next_id = max([int(i) for i in re.findall(r"C(\d+)", crystals)], default=0) + 1
    cid = f"C{next_id:03d}"
    files.append("crystals", f"\n| {cid} | {content} | — |\n")
    new_pending = pending_content.replace(match.group(1), "")
    files.write("pending", re.sub(r"\n\s*\n", "\n\n", new_pending).strip())
    engine._append_change_log("待确认卡确认", f"确认卡片 {card_id} 转为晶体 {cid}")
    return {"ok": True, "crystal_id": cid}


def parse_pending_card_block(files: Any, card_id: str) -> tuple:
    """解析单张待确认卡片，返回完整块、可确认内容和原始文件内容。"""
    pending_content = files.read("pending")
    match = re.search(
        rf"(##\s*{re.escape(card_id)}.*?)(?=\n## |\Z)",
        pending_content,
        re.DOTALL,
    )
    if not match:
        return None, None, pending_content
    block = match.group(1)
    content = None
    for pattern in ("- 标题：", "- 内容摘要：", "- 内容：", "- 生成晶体候选："):
        found = re.search(re.escape(pattern) + r"(.+)", block)
        if found:
            content = found.group(1).strip()
            break
    if not content:
        for line in block.split("\n"):
            line = line.strip()
            if line and not line.startswith("-") and not line.startswith("#"):
                content = line
                break
    return block, content, pending_content


def confirm_pending_card_with_content(
    files: Any,
    engine: Any,
    card_id: str,
    content: str,
    similar_fn: Any = None,
    force: bool = False,
) -> Dict[str, Any]:
    """确认待确认卡片并转为晶体，存在相似晶体时要求二次确认。"""
    block, _, pending_content = parse_pending_card_block(files, card_id)
    if not block:
        return {"error": f"未找到卡片 {card_id}"}
    content = normalize_text(content)
    if not content:
        return {"error": "无法解析卡片内容"}
    similar = similar_fn(content) if similar_fn else similar_crystals(engine, content)
    if similar and not force:
        return {"needs_confirm": True, "similar": similar}

    crystals = files.read("crystals")
    ids = re.findall(r"C(\d+)", crystals)
    next_id = max([int(i) for i in ids], default=0) + 1
    new_id = f"C{next_id:03d}"
    engine.create_crystal(
        crystal_id=new_id,
        content=content,
        links=[],
        source="pending_confirm",
    )
    new_pending = pending_content.replace(block, "")
    new_pending = re.sub(r"\n\s*\n", "\n\n", new_pending).strip()
    files.write("pending", new_pending)
    engine._append_change_log("待确认卡确认", f"确认卡片 {card_id} 转为晶体 {new_id}")
    return {"ok": True, "crystal_id": new_id}


def resolve_task(files: Any, engine: Any, task_id: str) -> None:
    cards = task_cards(files)
    found = False
    for card in cards:
        if card.get("id") == task_id:
            card["status"] = "done"
            found = True
    if not found:
        raise ValueError("任务不存在")
    save_task_cards(files, cards)
    engine._append_change_log("冲突解决", f"任务 {task_id} 已标记为已处理")


def ignore_task(files: Any, task_id: str) -> None:
    cards = task_cards(files)
    found = False
    for card in cards:
        if card.get("id") == task_id:
            card["status"] = "ignored"
            found = True
    if not found:
        raise ValueError("任务不存在")
    save_task_cards(files, cards)


def update_files(files: Any, engine: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    """把晶体化结果写入晶体/孔洞/状态文件，并追加变更日志。"""
    for c in result.get("new_crystals", []) or []:
        files.append(
            "crystals",
            f"\n| {c['id']} | {c['content']} | {', '.join(c.get('links', [])) or '—'} |\n",
        )
    for upd in result.get("updated_crystals", []) or []:
        content = files.read("crystals")
        pattern = rf"(\| {re.escape(upd['id'])} \| ).*?( \| .*? \|)"
        files.write("crystals", re.sub(pattern, rf"\1{upd['new_content']}\2", content))
    for hole in result.get("new_holes", []) or []:
        files.append(
            "holes",
            f"\n| {hole['id']} | {hole['content']} | {hole.get('urgency', 0.5)} |\n",
        )
    for upd in result.get("updated_holes", []) or []:
        content = files.read("holes")
        pattern = rf"(\| {re.escape(str(upd.get('id', '')))} \| ).*?(\| .*? \|)"
        files.write("holes", re.sub(pattern, rf"\1{upd.get('content', '')}\2", content))
    kept = []
    for card in result.get("pending_cards", []) or []:
        if append_pending_card(files, card):
            kept.append(card)
    result["pending_cards"] = kept
    change_entry = f"""### 变更摘要：{result.get('report_summary', '无摘要')}
- 新增晶体：{len(result.get('new_crystals', []))}
- 更新晶体：{len(result.get('updated_crystals', []))}
- 新增孔洞：{len(result.get('new_holes', []))}
- 更新孔洞：{len(result.get('updated_holes', []))}
- 冲突：{len(result.get('conflicts', []))}
- 待确认卡片：{len(result.get('pending_cards', []))}
"""
    engine._append_change_log("晶体化变更", change_entry)
    crystals_count = len(re.findall(r"^\| C\d+", files.read("crystals"), re.MULTILINE))
    holes_count = len(re.findall(r"^\| H\d+", files.read("holes"), re.MULTILINE))
    files.write(
        "state",
        f"""# 系统状态快照
**生成时间**: {datetime.now().isoformat()}
**晶体总数**: {crystals_count}
**孔洞总数**: {holes_count}
**最新变更摘要**: {result.get('report_summary', '无')}
""",
    )
    return result


def update_skill_content(
    config: Any,
    crystal_id: str,
    new_content: str,
) -> bool:
    """更新 Skill 目录中的 CRYSTAL.md 核心内容。"""
    skill_dir = config.DATA_ROOT / "skills" / crystal_id
    crystal_md = skill_dir / "CRYSTAL.md"
    if not crystal_md.exists():
        return False
    try:
        content = crystal_md.read_text(encoding="utf-8")
        pattern = r"(## 核心内容\s*\n+).*?(?=\n## |\Z)"
        replacement = f"\\1{new_content}\n\n"
        new_content_md = re.sub(pattern, replacement, content, flags=re.DOTALL)
        crystal_md.write_text(new_content_md, encoding="utf-8")
        return True
    except Exception as e:
        print(f"⚠️ 更新 Skill 内容失败 {crystal_id}: {e}")
        return False


def update_gui_files(
    files: Any,
    engine: Any,
    config: Any,
    ai_response: Dict[str, Any],
    update_skill_content_fn: Any,
    append_pending_card_fn: Any,
) -> None:
    """把晶体化结果写入文件系统，同时创建 Skill。"""
    if ai_response.get("new_crystals"):
        for c in ai_response["new_crystals"]:
            engine.create_crystal(
                crystal_id=c["id"],
                content=c["content"],
                links=c.get("links", []),
                input_conditions=c.get("input_conditions", []),
                execution_logic=c.get("execution_logic", ""),
                output_format=c.get("output_format", ""),
                validation_criteria=c.get("validation_criteria", []),
                source="crystallization",
            )
    if ai_response.get("updated_crystals"):
        for upd in ai_response["updated_crystals"]:
            content = files.read("crystals")
            pattern = rf"(\| {upd['id']} \| ).*?( \| .*? \|)"
            new = re.sub(pattern, rf"\1{upd['new_content']}\2", content)
            files.write("crystals", new)
            update_skill_content_fn(config, upd["id"], upd["new_content"])
    if ai_response.get("new_holes"):
        for hole in ai_response["new_holes"]:
            layer_name = {1: "第一层", 2: "第二层", 3: "第三层"}.get(
                hole.get("layer", 2),
                "第二层",
            )
            line = f"\n| {hole['id']} | {hole['content']} | {hole.get('urgency', 0.5)} |\n"
            content = files.read("holes")
            insert_after = f"## {layer_name}："
            if insert_after in content:
                parts = content.split(insert_after, 1)
                after = parts[1]
                next_heading = re.search(r"\n## ", after)
                if next_heading:
                    pos = len(parts[0]) + len(insert_after) + next_heading.start()
                else:
                    pos = len(content)
                new_content = content[:pos] + line + content[pos:]
                files.write("holes", new_content)
            else:
                files.append("holes", line)
    if ai_response.get("updated_holes"):
        for upd in ai_response["updated_holes"]:
            content = files.read("holes")
            pattern = rf"(\| {upd['id']} \| ).*?(\| .*? \|)"
            new = re.sub(pattern, rf"\1{upd['content']}\2", content)
            files.write("holes", new)
    if ai_response.get("pending_cards"):
        kept_cards = []
        for card in ai_response["pending_cards"]:
            if append_pending_card_fn(card):
                kept_cards.append(card)
        ai_response["pending_cards"] = kept_cards

    change_entry = f"""### 变更摘要：{ai_response.get('report_summary', '无摘要')}
- 新增晶体：{len(ai_response.get('new_crystals', []))}
- 更新晶体：{len(ai_response.get('updated_crystals', []))}
- 新增孔洞：{len(ai_response.get('new_holes', []))}
- 更新孔洞：{len(ai_response.get('updated_holes', []))}
- 冲突：{len(ai_response.get('conflicts', []))}
- 待确认卡片：{len(ai_response.get('pending_cards', []))}
"""
    engine._append_change_log("晶体化变更", change_entry)
    crystals_count = len(re.findall(r"^\| C\d+", files.read("crystals"), re.MULTILINE))
    holes_count = len(re.findall(r"^\| H\d+", files.read("holes"), re.MULTILINE))
    files.write(
        "state",
        f"""# 系统状态快照
**生成时间**: {datetime.now().isoformat()}
**晶体总数**: {crystals_count}
**孔洞总数**: {holes_count}
**最新变更摘要**: {ai_response.get('report_summary', '无')}
""",
    )

def system_status(files: Any) -> Dict[str, Any]:
    return {"content": files.read("state")}


def system_health(config: Any, health_checker: Any) -> Dict[str, Any]:
    return {
        "data_root": str(config.DATA_ROOT),
        "db_path": str(config.get_db_path()),
        "api_key_configured": bool(config.get_api_key()),
        "results": [item.__dict__ for item in health_checker.run()],
    }


def health_dashboard(engine: Any, auth: Any, user: Any) -> Dict[str, Any]:
    return {
        "user": {
            "username": user.username,
            "tier": user.tier,
            "trial_remaining": auth.get_trial_remaining(user.username),
        },
        "system": engine.get_audit_status(),
    }


def get_fingerprint(engine: Any) -> Dict[str, Any]:
    """获取当前认知指纹，异常时返回 None 而不是抛错。"""
    try:
        fp = engine.fingerprint_extractor.get_fingerprint()
        return {
            "fingerprint": {
                "risk_tolerance": fp.risk_tolerance,
                "innovation_preference": fp.innovation_preference,
                "decisiveness": fp.decisiveness,
                "preferred_role": fp.preferred_role,
                "conflict_resolution_style": fp.conflict_resolution_style,
                "attention_span": fp.attention_span,
                "context_preference": fp.context_preference,
                "confidence": fp.confidence,
                "total_interactions": fp.total_interactions,
                "last_updated": fp.last_updated,
            }
        }
    except Exception as e:
        return {"fingerprint": None, "error": str(e)}


def get_hebbian_stats(engine: Any) -> Dict[str, Any]:
    return engine.get_hebbian_stats()


def submit_hebbian_reward(
    engine: Any,
    kind: str,
    crystal_ids: Any = None,
    role_keys: Any = None,
    reward: Any = None,
    question: str = "",
    task_type: str = "",
) -> Dict[str, Any]:
    """提交 Hebbian 奖励信号并返回最新统计。"""
    rate = engine.record_hebbian_reward(
        kind,
        crystal_ids=crystal_ids,
        role_keys=role_keys,
        reward=reward,
        question=question,
        task_type=task_type,
    )
    return {
        "ok": True,
        "rate": round(rate, 3),
        "stats": engine.get_hebbian_stats(),
    }


def patch_asset(
    engine: Any,
    crystal_id: str,
    layer: str = "",
    fixed: Any = None,
) -> None:
    """调整晶体层级或固定状态，并写变更日志。"""
    state = engine.load_layer_state()
    layers = state.setdefault("layers", {})
    manual = state.setdefault("manual_override", {})
    if not layers:
        engine.update_crystal_layers()
        state = engine.load_layer_state()
        layers = state.setdefault("layers", {})
        manual = state.setdefault("manual_override", {})
    if crystal_id not in {c.id for c in engine.parse_crystals()}:
        raise ValueError("晶体不存在")
    if layer:
        if layer not in ("L1", "L2", "L3"):
            raise ValueError("层级必须是 L1/L2/L3")
        layers[crystal_id] = layer
    if fixed is not None:
        if fixed:
            layers[crystal_id] = "L1"
            manual[crystal_id] = "L1_fixed"
        else:
            manual.pop(crystal_id, None)
    state["last_accessed"][crystal_id] = datetime.now().date().isoformat()
    engine.save_layer_state(state)
    engine._append_change_log("Web层级变更", f"晶体 {crystal_id} -> {layers.get(crystal_id)}")


def delete_asset(files: Any, engine: Any, crystal_id: str) -> bool:
    """从晶体文件和层级状态中删除一个晶体。"""
    content = files.read("crystals")
    new = re.sub(
        rf"\| {re.escape(crystal_id)} \|.*?\|\n", "", content, flags=re.MULTILINE
    )
    if new == content:
        return False
    files.write("crystals", new)
    state = engine.load_layer_state()
    for key in ("layers", "heat_map", "last_accessed", "manual_override"):
        state.get(key, {}).pop(crystal_id, None)
    engine.save_layer_state(state)
    engine._append_change_log("Web删除晶体", f"删除 {crystal_id}")
    return True


def ignore_pending_card(files: Any, card_id: str) -> None:
    """忽略一条待确认卡片。"""
    pending_content = files.read("pending")
    new = re.sub(
        rf"## {re.escape(card_id)}.*?(?=\n## |\Z)",
        "",
        pending_content,
        flags=re.DOTALL,
    )
    files.write("pending", re.sub(r"\n\s*\n", "\n\n", new).strip())


def force_archive_holes(
    file_io: Any,
    holes: List[Dict[str, Any]],
    on_log: Any,
) -> int:
    """把未归档 L3 孔洞转为待确认卡片。"""
    for hole in holes:
        card_id = f"PENDING-ARCHIVE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        content = f"""## {card_id}
- 类型：强制归档·L3孔洞
- 孔洞ID：{hole.get('id', '未知')}
- 内容：{hole.get('content', '')}
- 紧迫度：{hole.get('urgency', 0.5)}
- 建议：此孔洞来自辩论沉淀，请确认是否需要进一步探索或转为晶体。
"""
        file_io.append("pending", "\n" + content + "\n")
        on_log(f"  ✅ 生成待确认卡片 {card_id}", "success")
    return len(holes)


# ===== ? application/services.py ?? =====

def list_skills(engine: Any) -> Dict[str, Any]:
    try:
        skills = engine.get_all_skills()
        return {"skills": skills, "total": len(skills)}
    except Exception as e:
        return {"error": str(e), "skills": [], "total": 0}

def get_skill(engine: Any, crystal_id: str) -> Dict[str, Any]:
    try:
        skill_path = engine.get_skill_path(crystal_id)
        if not skill_path:
            raise ValueError(f"Skill {crystal_id} 不存在")
        crystal = engine.get_skill_crystal(crystal_id)
        validation = engine.validate_skill(crystal_id)
        file_names = [f.name for f in skill_path.iterdir() if f.is_file()]
        refs_dir = skill_path / "references"
        references = (
            [f.name for f in refs_dir.iterdir() if f.is_file()]
            if refs_dir.exists()
            else []
        )
        return {
            "id": crystal_id,
            "path": str(skill_path),
            "files": file_names,
            "references": references,
            "crystal": {
                "content": crystal.content if crystal else "",
                "layer": crystal.layer.value if crystal else "unknown",
            }
            if crystal
            else None,
            "validation": validation,
        }
    except ValueError:
        raise
    except Exception as e:
        return {"error": str(e)}

def validate_skills(engine: Any, crystal_ids: Any = None) -> Dict[str, Any]:
    try:
        if crystal_ids:
            result = engine.validate_skills_batch(crystal_ids)
        else:
            all_skills = engine.get_all_skills()
            result = engine.validate_skills_batch(all_skills)
        return result
    except Exception as e:
        return {"error": str(e), "total": 0, "valid_count": 0, "results": {}}

def validate_single_skill(engine: Any, crystal_id: str) -> Dict[str, Any]:
    try:
        return engine.validate_skill(crystal_id)
    except Exception as e:
        return {"error": str(e), "valid": False}

def run_skill_migration(set_job: Any, log: Any) -> None:
    from scripts.migrate_crystals_to_skills import CrystalToSkillMigrator

    migrator = CrystalToSkillMigrator()
    result = migrator.run()
    set_job(status="done", progress=100, result=result)
    log(f"迁移完成: {result.get('migrated', 0)} 条晶体", "success")

def run_skill_migration_gui(
    migrator_factory: Any,
    config: Any,
    on_log: Any,
    on_ready: Any,
) -> None:
    """执行晶体到 Skill 的迁移，结果通过回调汇报。"""
    try:
        migrator = migrator_factory()
        result = migrator.run()
        if result["success"]:
            on_log(f"✅ 迁移完成: {result['migrated']} 条晶体", "success")
            on_log(f"   Skills 目录: {config.DATA_ROOT / 'skills'}", "system")
        else:
            on_log(f"⚠️ 迁移部分失败: {result['failed']} 条", "warning")
            for fail in result.get("failed_details", []):
                on_log(f"   {fail['id']}: {fail['error']}", "error")
    except Exception as e:
        on_log(f"❌ 迁移失败: {e}", "error")
        traceback.print_exc()
    finally:
        on_ready()

def run_skill_export(
    engine: Any,
    crystal_id: str,
    output_dir: Any,
) -> tuple:
    """导出单个晶体为 Skill 目录。"""
    from scripts.export_agents import export_skill

    output_path = Path(output_dir) / f"skill_{crystal_id}"
    result = export_skill(crystal_id, str(output_path), engine)
    return result, output_path

def run_validate_skills(
    engine: Any,
    on_log: Any,
    on_ready: Any,
) -> None:
    """验证所有 Skill 并输出结果。"""
    try:
        all_skills = engine.get_all_skills()
        if not all_skills:
            on_log("⚠️ 没有找到任何 Skill", "warning")
            return
        on_log(f"📊 发现 {len(all_skills)} 个 Skill，开始验证...", "system")
        summary = engine.get_skill_validation_summary()
        on_log("", "system")
        on_log("=" * 60, "system")
        on_log("📊 Skill 验证结果", "system")
        on_log("=" * 60, "system")
        on_log(f"  总计: {summary['total']}", "system")
        on_log(f"  ✅ 通过: {summary['valid']}", "success")
        on_log(
            f"  ❌ 未通过: {summary['invalid']}",
            "error" if summary["invalid"] > 0 else "system",
        )
        on_log("", "system")
        for cid, details in summary["details"].items():
            status = "✅" if details["valid"] else "❌"
            on_log(
                f"  {status} {cid} (耗时 {details.get('execution_time', 0):.2f}s)",
                "system",
            )
    except Exception as e:
        on_log(f"❌ 验证失败: {e}", "error")
        traceback.print_exc()
    finally:
        on_ready()

def create_twin_workbench(
    engine: Any,
    ai: Any,
) -> Any:
    """创建替身工作台，缺省替身时补齐三个基础角色。"""
    workbench = TwinWorkbench(engine, ai)
    if not workbench.get_all_twins():
        workbench.create_twin("决策替身", "决策替身")
        workbench.create_twin("学习替身", "学习替身")
        workbench.create_twin("社交替身", "社交替身")
    return workbench

def run_contribute_crystal(
    engine: Any,
    crystal_id: str,
    user_id: str,
    is_anonymous: bool,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        result = engine.contribute_crystal(crystal_id, user_id, is_anonymous)
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()

def run_inherit_seeds(
    engine: Any,
    user_id: str,
    limit: int,
    on_done: Any,
    on_error: Any,
    on_ready: Any,
) -> None:
    try:
        result = engine.inherit_seeds(user_id, limit)
        on_done(result)
    except Exception as e:
        on_error(e)
        on_ready()

def vote_role(
    engine: Any,
    role_key: str,
    support: Any,
) -> tuple:
    """记录用户对辩论角色的支持/反对/中立。"""
    new = engine.vote_role(role_key, support)
    label = "中立" if support is None else ("支持" if support else "反对")
    return new, label

def run_chat_task(
    db: Any,
    engine: Any,
    ai_client_factory: Any,
    session_id: str,
    effective_key: str,
    log: Any = None,
) -> Dict[str, Any]:
    """执行一次普通对话，追加用户/助手消息并返回回复。"""
    ai = ai_client_factory(api_key=effective_key)
    _name, history, _ = db.get_session(session_id)
    l0_holes, l1_crystals = engine.get_attention_context()
    context = (
        f"\n[注意力上下文] 当前核心孔洞："
        f"{', '.join([h.content[:50] for h in l0_holes])}\n"
        f"L1晶体数量：{len(l1_crystals)} 条\n"
    )
    if log:
        log("AI 思考中...")
    reply = ai.chat_with_history(history, context=context)
    scored_reply = reply + score_line(reply)
    add_session_message(db, session_id, "assistant", scored_reply)
    return {
        "session_id": session_id,
        "reply": scored_reply,
        "score": score_payload(reply),
    }

def run_crystallize_task(
    db: Any,
    engine: Any,
    ai_client_factory: Any,
    session_id: str,
    effective_key: str,
    user_input: str,
    fast_mode: bool,
    prompt_builder: Any,
    normalizer: Any,
    log: Any = None,
) -> Dict[str, Any]:
    """生成晶体化预览，返回标准化后的结构化结果。"""
    ai = ai_client_factory(api_key=effective_key)
    search_res = (
        "（快速模式：跳过外部搜索）"
        if fast_mode
        else "（Web v1：外部搜索将在下一阶段增强）"
    )
    prompt = prompt_builder(user_input, search_res)
    if log:
        log("晶体化预览生成中...")
    raw = ai.chat_json(prompt)
    if "error" in raw:
        raise RuntimeError(raw["error"])
    normalized = normalizer(raw)
    if "error" in normalized:
        raise RuntimeError(normalized["error"])
    return {"session_id": session_id, "preview": normalized}

def run_file_chat_task(
    db: Any,
    ai_client_factory: Any,
    batch_processor_factory: Any,
    session_id: str,
    effective_key: str,
    file_path: Any,
    filename: str,
    log: Any = None,
) -> Dict[str, Any]:
    """读取文件内容并让 AI 基于文件回答，消息回写会话。"""
    ai = ai_client_factory(api_key=effective_key)
    batch = batch_processor_factory(ai, log)
    units = batch.extract_text_from_file(str(file_path))
    if not units:
        raise RuntimeError("文件无有效内容或读取失败")
    content = units[0].strip()
    if len(content) > 10000:
        content = content[:10000] + "\n...（内容过长已截断）"
    user_msg = (
        f"[文件内容] {filename} 的内容如下：\n\n{content}\n\n"
        "请基于以上文件内容回答。"
    )
    add_session_message(db, session_id, "user", user_msg)
    _name, history, _ = db.get_session(session_id)
    reply = ai.chat_with_history(history)
    scored_reply = reply + score_line(reply)
    add_session_message(db, session_id, "assistant", scored_reply)
    return {
        "session_id": session_id,
        "reply": scored_reply,
        "score": score_payload(reply),
    }

def run_batch_process_task(
    ai_client_factory: Any,
    batch_processor_factory: Any,
    effective_key: str,
    folder: Any,
    mode: str,
    fast_mode: bool,
    inject_history: bool,
    session_id: str,
    progress: Any,
    stop_flag: Any,
    history_adder: Any,
    log: Any = None,
) -> Dict[str, Any]:
    """执行批量处理任务，进度与历史回写由调用方注入。"""
    ai = ai_client_factory(api_key=effective_key)
    batch = batch_processor_factory(ai, log)

    def progress_cb(value):
        progress(max(5, min(99, int(value))))

    def hist(role, content):
        if inject_history and session_id:
            history_adder(session_id, role, content)

    batch.process_folder(
        str(folder),
        mode,
        fast_mode,
        progress_cb,
        stop_flag,
        hist,
    )
    return {"folder": str(folder)}

def run_daily_plan_task(
    engine: Any,
    ai_client_factory: Any,
    fetcher_factory: Any,
    planner_factory: Any,
    effective_key: str,
    intent_keywords: List[str],
    time_budget_seconds: int,
    stop_flag: Any,
    progress_callback: Any,
    log: Any,
    status_callback: Any,
) -> Dict[str, Any]:
    """执行每日计划，业务逻辑全部位于服务层。"""
    ai = ai_client_factory(api_key=effective_key)
    fetcher = fetcher_factory()
    planner = planner_factory(engine, ai, fetcher, log, status_callback)
    return planner.run(
        intent_keywords=intent_keywords,
        time_budget_seconds=time_budget_seconds,
        stop_flag=stop_flag,
        progress_callback=progress_callback,
    )


def attach_debate_score(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """给辩论结果附加八维评分：写回 board_version 并返回结构化评分。"""
    final_schema = result.get("final_schema")
    if isinstance(final_schema, dict):
        board = final_schema.get("board_version") or result.get("board_version") or ""
        employee = final_schema.get("employee_version") or result.get("employee_version") or ""
        novice = final_schema.get("novice_version") or result.get("novice_version") or ""
        expert = final_schema.get("expert_version") or result.get("expert_version") or ""
    else:
        board = result.get("board_version") or result.get("answer") or ""
        employee = result.get("employee_version") or ""
        novice = result.get("novice_version") or ""
        expert = result.get("expert_version") or ""
    if not board:
        return None
    debate_text = "\n".join([board, employee, novice, expert])
    payload = score_payload(debate_text)
    scored_board = board + score_line(debate_text)
    if isinstance(final_schema, dict):
        final_schema["board_version"] = scored_board
    result["board_version"] = scored_board
    result["answer"] = scored_board
    result["score"] = payload
    return payload


def reply_with_score(reply: str) -> str:
    """给普通回复追加八维评分行。"""
    return reply + score_line(reply)


def clamp_debate_rounds(value: Any) -> int:
    """把辩论轮次限制在 2~12。"""
    try:
        return max(2, min(12, int(value)))
    except (TypeError, ValueError):
        return 2


def build_session_context(history: Any, current_input: str, limit: int = 20) -> str:
    """从会话历史构建最近上下文（深度推理用）。"""
    if not history:
        return current_input
    lines = []
    for role, content in history[-limit:]:
        if role == "user" and current_input.strip() and current_input.strip() in content:
            continue
        label = "用户" if role == "user" else "AI"
        text = re.sub(r"\s+", " ", str(content)).strip()
        if text:
            lines.append(f"{label}: {text[:900]}")
    if not lines:
        return current_input
    context = "【本会话最近上下文】\n" + "\n".join(lines)
    return context + f"\n\n【当前问题】\n{current_input}"


def run_gui_chat_task(
    engine: Any,
    ai: Any,
    api_key: str,
    cur_history: List[Any],
    on_log: Any,
    on_done: Any,
) -> None:
    """GUI 普通对话的后端逻辑：注意力上下文、认知风格、质量门。"""
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key
    l0_holes, l1_crystals = engine.get_attention_context()
    context = (
        f"\n[注意力上下文] 当前核心孔洞："
        f"{', '.join([h.content[:50] for h in l0_holes])}\n"
        f"L1晶体数量：{len(l1_crystals)} 条\n"
    )
    try:
        fp = engine.fingerprint_extractor.get_fingerprint()
        ops = engine.fingerprint_extractor.get_cognitive_operators(fp)
        on_log(f"🧠 注入认知风格：{ops}", "system")
    except Exception:
        ops = "[思维模式：平衡] [论证偏好：平衡] [输出偏好：平衡]"
        on_log(f"⚠️ 认知风格加载失败，使用默认：{ops}", "warning")

    base_system = "你是认知晶体树的AI协作者，请友好自然地回答问题。"
    system_with_style = (
        f"{base_system}\n\n【用户认知风格】{ops}\n"
        "请根据这些偏好调整你的表达方式，使回答更贴近用户的思维习惯。"
    )
    reply = ai.chat_with_history(cur_history, system=system_with_style, context=context)

    g2_result = engine.quality_gate_g2(reply, {"audit_score": 0.5})
    if g2_result["passed"]:
        on_log(f"✅ G2 通过: {g2_result['reason']}", "system")
    else:
        on_log(f"⚠️ G2 提醒: {g2_result['reason']}", "warning")
    on_done(reply_with_score(reply))


def run_gui_file_chat_task(
    engine: Any,
    ai: Any,
    api_key: str,
    cur_history: List[Any],
    on_done: Any,
) -> None:
    """文件对话的后端逻辑：注意力上下文 + AI 回复。"""
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key
    l0_holes, l1_crystals = engine.get_attention_context()
    ctx = (
        f"\n[注意力上下文] 当前核心孔洞："
        f"{', '.join([h.content[:50] for h in l0_holes])}\n"
        f"L1晶体数量：{len(l1_crystals)} 条\n"
    )
    reply = ai.chat_with_history(cur_history, context=ctx)
    on_done(reply_with_score(reply))


def run_gui_batch_task(
    batch_processor: Any,
    api_key: str,
    folder: str,
    mode: str,
    fast_mode: bool,
    progress: Any,
    stop: Any,
    history_cb: Any,
    on_done: Any,
) -> None:
    """GUI 批量处理的后端逻辑：设置 Key 后交给批处理器。"""
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key
    batch_processor.process_folder(
        folder,
        mode,
        fast_mode,
        progress,
        stop,
        history_cb,
    )
    on_done()


def build_pending_card_view_data(files: Any) -> List[Dict[str, Any]]:
    """解析待确认卡片，供 GUI 渲染列表。"""
    content = files.read("pending")
    cards = re.findall(r"## (PENDING-\d+-\d+)\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    result = []
    for cid, body in cards:
        card_type = title = source = content_text = ""
        for line in body.split("\n"):
            if line.startswith("- 类型："):
                card_type = line.replace("- 类型：", "").strip()
            elif line.startswith("- 标题："):
                title = line.replace("- 标题：", "").strip()
            elif line.startswith("- 来源："):
                source = line.replace("- 来源：", "").strip()
            elif line.startswith("- 内容摘要："):
                content_text = line.split("：", 1)[-1].strip()
            elif line.startswith("- 内容："):
                content_text = line.split("：", 1)[-1].strip()
            elif line.startswith("- 生成晶体候选："):
                content_text = line.split("：", 1)[-1].strip()
        if not title:
            title = content_text[:50] if content_text else cid
        result.append(
            {
                "id": cid,
                "type": card_type,
                "title": title,
                "source": source,
                "content": content_text,
            }
        )
    return result


def format_crystal_update_preview(
    result: Dict[str, Any],
    similar_fn: Any = None,
) -> str:
    """格式化晶体化结果预览，相似度通过回调注入。"""
    lines = [f"摘要：{result.get('report_summary', '晶体化完成')}", ""]
    lines.append(f"新增晶体：{len(result.get('new_crystals', []))}")
    for c in result.get("new_crystals", []):
        lines.append(
            f"- {c['id']} | {c['content']} | links={','.join(c.get('links', [])) or '—'}"
        )
        similar = similar_fn(c["content"]) if similar_fn else []
        if similar:
            lines.append("  可能重复：")
            for score, old in similar:
                lines.append(f"  * {old.id} ({score:.2f}) {old.content[:60]}")
    lines.append("")
    lines.append(f"更新晶体：{len(result.get('updated_crystals', []))}")
    for c in result.get("updated_crystals", []):
        lines.append(f"- {c['id']} -> {c.get('new_content', '')}")
    lines.append("")
    lines.append(f"新增孔洞：{len(result.get('new_holes', []))}")
    for h in result.get("new_holes", []):
        lines.append(
            f"- {h['id']} | {h['content']} | urgency={h.get('urgency', 0.5)} "
            f"| layer={h.get('layer', 2)}"
        )
    lines.append("")
    lines.append(f"待确认卡片：{len(result.get('pending_cards', []))}")
    for card in result.get("pending_cards", []):
        lines.append(
            f"- {card.get('type', '晶体候选')} | {card.get('content', '')[:100]}"
        )
    lines.append("")
    lines.append(f"冲突：{len(result.get('conflicts', []))}")
    for c in result.get("conflicts", []):
        lines.append(f"- {c.get('a')} vs {c.get('b')} | {c.get('reason', '')}")
    return "\n".join(lines)


def run_gui_crystal_task(
    engine: Any,
    ai: Any,
    api_key: str,
    user_input: str,
    fast_mode: bool,
    extract_keywords: Any,
    search_fn: Any,
    prompt_builder: Any,
    normalizer: Any,
    on_log: Any,
    on_preview: Any,
    on_done: Any,
) -> None:
    """GUI 晶体化的后端逻辑：外部搜索、Prompt、AI JSON、标准化。"""
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key
    try:
        l0_holes, l1_crystals = engine.get_attention_context()
        if fast_mode:
            search_res = "（快速模式：跳过外部搜索）"
        else:
            keywords = extract_keywords(user_input)
            search_res = search_fn(keywords) if keywords else "（关键词提取失败）"
        prompt = prompt_builder(user_input, search_res, l0_holes, l1_crystals)
        result = ai.chat_json(prompt)
        if "error" in result:
            on_log(f"❌ 晶体化失败：{result['error']}", "error")
            return
        normalized = normalizer(result)
        if "error" in normalized:
            on_log(f"❌ 标准化失败：{normalized['error']}", "error")
            return
        on_preview(normalized)
    except Exception as e:
        on_log(f"❌ 出错：{e}", "error")
        traceback.print_exc()
    finally:
        on_done()


def wisdom_commons_display(engine: Any) -> List[str]:
    """生成智慧公库列表的展示行。"""
    commons = engine._load_wisdom_commons()
    crystals = commons.get("crystals", [])
    if not crystals:
        return ["（公库暂无晶体，请贡献）"]
    lines = []
    for crystal in crystals:
        status = crystal.get("status", "active")
        status_icon = "✅" if status == "active" else "⏸"
        cid = crystal.get("crystal_id", "未知")
        content = crystal.get("content", "")[:40]
        score = crystal.get("score", 0)
        usage = crystal.get("usage_count", 0)
        lines.append(f"{cid} | {content}... | 评分:{score:.0f} | 使用:{usage}次 {status_icon}")
    return lines


def question_display_lines(history: List[Any], labels: List[Any]) -> List[str]:
    """把会话历史中的用户消息转换为问题列表展示行。"""
    lines = []
    q_num = 1
    for i, (role, content) in enumerate(history):
        if role != "user":
            continue
        label = labels[i] if i < len(labels) else None
        if label:
            display = f"{q_num}. {label}"
        elif content.startswith("[晶体化] "):
            body = content[len("[晶体化] "):]
            display = f"{q_num}. [晶体化] {body[:44]}{'...' if len(body) > 44 else ''}"
        elif content.startswith("[深度推理-多角色] "):
            body = content[len("[深度推理-多角色] "):]
            display = f"{q_num}. [多角色] {body[:40]}{'...' if len(body) > 40 else ''}"
        elif content.startswith("[深度推理] "):
            body = content[len("[深度推理] "):]
            display = f"{q_num}. [深度推理] {body[:43]}{'...' if len(body) > 43 else ''}"
        elif content.startswith("[辩论增强] "):
            body = content[len("[辩论增强] "):]
            display = f"{q_num}. [辩论] {body[:43]}{'...' if len(body) > 43 else ''}"
        elif content.startswith("[卢氏注意力增强 + 辩论增强] "):
            body = content[len("[卢氏注意力增强 + 辩论增强] "):]
            display = f"{q_num}. [卢氏+辩论] {body[:34]}{'...' if len(body) > 34 else ''}"
        elif content.startswith("[卢氏注意力增强] "):
            body = content[len("[卢氏注意力增强] "):]
            display = f"{q_num}. [卢氏] {body[:41]}{'...' if len(body) > 41 else ''}"
        elif content.startswith("[文件内容] "):
            body = content[len("[文件内容] "):]
            display = f"{q_num}. [文件] {body[:40]}{'...' if len(body) > 40 else ''}"
        else:
            display = f"{q_num}. {content[:50]}{'...' if len(content) > 50 else ''}"
        lines.append(display)
        q_num += 1
    return lines


def resolve_round_titles(
    is_first: bool,
    user_msg: str,
    reply: str,
    existing_titles: List[str],
    ai_client_factory: Any,
    log: Any = None,
    labels: List[Any] = None,
) -> tuple:
    """解析会话标题与轮次标题；首轮可能生成两者，非首轮只生成本轮标题。"""
    if not user_msg:
        return "", ""
    if is_first:
        sess_title, round_label = generate_dual_titles(
            user_msg,
            reply,
            existing_titles,
            ai_client_factory,
            log,
        )
        if not sess_title:
            fallback = fallback_session_title(user_msg)
            if fallback:
                original = fallback
                counter = 2
                title_set = set(existing_titles)
                while fallback in title_set:
                    fallback = f"{original} ({counter})"
                    counter += 1
                if len(fallback) > 15:
                    fallback = fallback[:12] + "..."
                sess_title = fallback
        return sess_title, round_label
    round_label = generate_round_label_simple(
        user_msg,
        ai_client_factory,
        labels or [],
        log,
    )
    return "", round_label


def run_deep_reasoning_task(
    engine: Any,
    ai_client_factory: Any,
    debate_engine_factory: Any,
    job_id: str,
    session_id: str,
    effective_key: str,
    mode: str,
    user_input: str,
    max_rounds: Any,
    roles_loader: Any,
    history_context_builder: Any,
    add_message: Any,
    log: Any,
) -> Dict[str, Any]:
    """执行深度推理：辩论模式走 DebateEngine，其余走联想增强单路径。"""
    ai = ai_client_factory(api_key=effective_key)
    effective_mode = "debate_full" if mode in ("auto", "multi_role") else mode
    reason_input = history_context_builder(session_id, user_input)
    max_rounds = max(2, min(12, int(max_rounds or 2)))

    if effective_mode in ("debate_light", "debate_full", "lushi_sampling"):
        log("晶体树辩论引擎启动中...")
        debate = debate_engine_factory(ai, roles_loader(), log)
        result = debate.run(
            reason_input,
            mode=effective_mode,
            max_rounds=max_rounds,
        )

        try:
            _schema_defaults = {
                "meta": {},
                "role_contributions": {},
                "judge_performance_board": [],
                "judge_final_verdict": "",
                "judge_rejected_details": "",
                "round_by_round": [],
                "board_version": "",
                "employee_version": "",
                "novice_version": "",
                "expert_version": "",
                "elegant_epilogue": "",
                "dashboard_stats": {},
            }
            _schema_data = result.get("final_schema") or {}
            final_schema = SimpleNamespace(
                **{
                    key: _schema_data.get(key, default)
                    for key, default in _schema_defaults.items()
                }
            )

            result["final_schema"] = _schema_data
            result["board_version"] = final_schema.board_version
            result["employee_version"] = final_schema.employee_version
            result["novice_version"] = final_schema.novice_version
            result["expert_version"] = final_schema.expert_version
            result["elegant_epilogue"] = final_schema.elegant_epilogue
            result["dashboard_stats"] = final_schema.dashboard_stats

            result["judge_audit"] = {
                "by_rule": final_schema.judge_performance_board,
                "summary": final_schema.judge_final_verdict,
                "rejected_items": final_schema.judge_rejected_details,
            }
            result["round_by_round"] = final_schema.round_by_round
            result["answer"] = final_schema.board_version

            payload = attach_debate_score(result)
            scored_board = result["board_version"]

            add_message(session_id, "assistant", scored_board)
            log("✅ V3.0 结构化输出生成完成", "success")

            result["final"] = {
                "rigid_core": {
                    "decision_summary": (
                        scored_board[:200]
                        if scored_board
                        else "（决策摘要生成中）"
                    ),
                    "core_adoptions": [
                        f"{r.get('role', '')}：{r.get('brief_reason', '')}"
                        for r in final_schema.judge_performance_board
                        if r.get("status") in ["adopted", "conditional"]
                    ],
                    "key_synthesis": (
                        final_schema.expert_version[:500]
                        if final_schema.expert_version
                        else "（决策逻辑待补充）"
                    ),
                    "risks_and_boundaries": ["（风险分析待补充）"],
                },
                "one_sentence_conclusion": (
                    scored_board[:50]
                    if scored_board
                    else "（结论待补充）"
                ),
                "student_friendly_answer": final_schema.novice_version
                or "（通俗解读待补充）",
                "teacher_detail": final_schema.expert_version
                or "（详细复盘待补充）",
                "soft_wrap": final_schema.employee_version
                or "（精简版待补充）",
                "judge_audit": {
                    "by_rule": final_schema.judge_performance_board,
                    "summary": final_schema.judge_final_verdict,
                },
                "dashboard_stats": final_schema.dashboard_stats,
            }

            return {
                "job_id": job_id,
                "session_id": session_id,
                "score": payload or {},
                "summary": {
                    "board": scored_board,
                    "employee": final_schema.employee_version,
                    "novice": final_schema.novice_version,
                    "expert": final_schema.expert_version,
                    "elegant": final_schema.elegant_epilogue,
                },
                "full": {
                    "judge_audit": {
                        "by_rule": final_schema.judge_performance_board,
                        "summary": final_schema.judge_final_verdict,
                        "rejected_details": final_schema.judge_rejected_details,
                    },
                    "dashboard_stats": final_schema.dashboard_stats,
                    "round_by_round": final_schema.round_by_round,
                    "meta": final_schema.meta,
                    "role_contributions": final_schema.role_contributions,
                },
            }
        except Exception as e:
            log(f"⚠️ 输出编排数据读取失败: {e}，降级返回原始数据", "error")
            traceback.print_exc()
            add_message(session_id, "assistant", result.get("answer", "输出异常"))
            return {
                "job_id": job_id,
                "session_id": session_id,
                "reply": result.get("answer", "输出异常"),
                "full": result,
            }

    # 单路径深度推理
    assoc = engine.get_associative_crystals(user_input, top_k=5)
    crystal_ctx = "\n".join([f"- [{c.id}] {c.content}" for c in assoc]) or "（无相关晶体）"
    log("联想增强推理中...")
    raw = ai.chat(
        reason_input,
        system="请结合本会话上下文回答当前问题，给出最直接的答案。",
    )
    comment = ai.chat(
        f"用户问题与上下文：{reason_input}\n裸模型回答：{raw}\n"
        f"相关晶体树知识：\n{crystal_ctx}\n"
        "请指出晶体支持、反驳或补充了哪些视角。",
        system="你是晶体树的知识审计员。",
    )
    final = ai.chat(
        f"原始问题与上下文：{reason_input}\n裸模型回答：{raw}\n"
        f"晶体树评论：{comment}\n请综合两者给出最终答案。",
        system="你是认知晶体树的综合推理者。",
    )
    reply = (
        f"【裸模型回答】\n{raw}\n\n【晶体树评论（联想增强）】\n{comment}\n\n"
        f"【综合最终答案】\n{final}"
    )
    scored_reply = reply_with_score(reply)
    add_message(session_id, "assistant", scored_reply)
    return {
        "session_id": session_id,
        "reply": scored_reply,
        "score": score_payload(reply),
    }

def run_auto_health_fix(
    engine: Any,
    ai: Any,
    fetcher: Any,
    log: Any,
    update_status: Any,
    on_log: Any,
    on_done: Any,
) -> None:
    """自动健康修复：每日计划、冷晶体归档、审计重平衡。"""
    try:
        log("  📅 执行每日计划...", "system")
        planner = DailyPlanner(engine, ai, fetcher, log, update_status)
        planner.run(
            intent_keywords=["晶体化", "知识积累", "归档"],
            time_budget_seconds=300,
            stop_flag=lambda: False,
        )
        log("  📦 执行冷晶体归档...", "system")
        archived = engine.archive_cold_crystals()
        log(f"    归档 {len(archived)} 条冷晶体", "system")
        log("  ⚖️ 运行审计重平衡...", "system")
        engine.run_audit_now()
        on_log("✅ 自动修复完成！", "success")
        on_done(len(archived))
    except Exception as e:
        on_log(f"❌ 自动修复失败: {e}", "error")
        on_done(0)

def daily_plan_is_run_today(
    engine: Any,
    ai: Any,
    fetcher: Any,
    log: Any,
    update_status: Any,
) -> bool:
    planner = DailyPlanner(engine, ai, fetcher, log, update_status)
    return planner.is_today_run()

def polish_report(
    full_report: str,
    ai_client: Any,
    log: Any = None,
) -> str:
    """压缩完整报告到硬契约字数，并记录进度。"""
    if log:
        log(f"📝 润色师启动：完整版 → {COMPRESSED_REPORT_TARGET}字压缩版")
    result = polish_report_markdown(
        full_report,
        ai_client=ai_client,
        max_len=COMPRESSED_REPORT_TARGET,
    )
    if log:
        log(f"✅ 压缩版完成：{len(result)} 字")
    return result

def build_performance_table(performance_board: List[Dict]) -> List[str]:
    """构建绩效看板的纯文本表格。"""
    if not performance_board:
        return ["（绩效看板数据缺失）"]
    performance_board = ensure_performance_board(list(performance_board))
    rows = []
    for item in performance_board:
        role = item.get("role", "未知")[:10]
        contrib = str(item.get("contribution_percent", 0))
        kpi = str(item.get("kpi_score", 0))
        status = item.get("status", "暂缓")
        reason = item.get("reason", "")[:15]
        status_icon = {
            "采纳": "✅",
            "附条件": "⚠️",
            "暂缓": "⏸",
            "驳回": "❌",
        }.get(status, "•")
        status_display = f"{status_icon}{status}"
        rows.append(
            {
                "role": role,
                "contrib": contrib,
                "kpi": kpi,
                "status": status_display,
                "reason": reason,
            }
        )
    max_role = max([len(r["role"]) for r in rows] + [4])
    max_contrib = max([len(r["contrib"]) for r in rows] + [5])
    max_kpi = max([len(r["kpi"]) for r in rows] + [5])
    max_status = max([len(r["status"]) for r in rows] + [4])
    max_reason = max([len(r["reason"]) for r in rows] + [6])
    sep = (
        "+"
        + "-" * (max_role + 2)
        + "+"
        + "-" * (max_contrib + 2)
        + "+"
        + "-" * (max_kpi + 2)
        + "+"
        + "-" * (max_status + 2)
        + "+"
        + "-" * (max_reason + 2)
        + "+"
    )
    header = (
        "| "
        + "角色".ljust(max_role)
        + " | "
        + "贡献度".ljust(max_contrib)
        + " | "
        + "KPI".ljust(max_kpi)
        + " | "
        + "状态".ljust(max_status)
        + " | "
        + "核心理由".ljust(max_reason)
        + " |"
    )
    lines = [sep, header, sep]
    for row in rows:
        line = (
            "| "
            + row["role"].ljust(max_role)
            + " | "
            + row["contrib"].rjust(max_contrib)
            + "% | "
            + row["kpi"].rjust(max_kpi)
            + "/10 | "
            + row["status"].ljust(max_status)
            + " | "
            + row["reason"].ljust(max_reason)
            + " |"
        )
        lines.append(line)
    lines.append(sep)
    return lines

def save_report_to_desktop(
    question: str,
    result: Dict[str, Any],
    board_version: str,
    employee_version: str,
    novice_version: str,
    expert_version: str,
    judge_audit: Dict[str, Any],
    ai_client: Any = None,
    log: Any = None,
    desktop_dir: Path = None,
) -> Dict[str, str]:
    """把辩论报告以压缩版/原始版/速览版三份写入输出目录。"""
    desktop = desktop_dir or Config.REPORT_OUTPUT_DIR
    desktop.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_report = build_debate_report_markdown(
        question,
        result,
        board_version,
        employee_version,
        novice_version,
        expert_version,
        judge_audit,
    )
    polished_report = polish_report(full_report, ai_client, log)
    compressed_path = desktop / f"辩论报告_压缩版_{timestamp}.md"
    compressed_path.write_text(polished_report, encoding="utf-8")
    original_path = desktop / f"辩论报告_原始_{timestamp}.md"
    original_path.write_text(full_report, encoding="utf-8")
    quick_report = build_quick_view_report(
        full_report,
        ai_client=ai_client,
        max_chars=QUICK_VIEW_TARGET,
    )
    quick_path = desktop / f"辩论报告_速览版_{timestamp}.md"
    quick_path.write_text(quick_report, encoding="utf-8")
    return {
        "compressed": str(compressed_path),
        "original": str(original_path),
        "quick": str(quick_path),
    }

def generate_dual_titles(
    user_msg: str,
    ai_reply: str,
    existing_titles: List[str],
    api_key_factory: Any,
    log: Any = None,
) -> tuple:
    """生成会话标题与本轮标题，并做硬去重。"""
    if not user_msg or not ai_reply:
        return "", ""
    ai_summary = ai_reply[:800]
    if len(ai_reply) > 800:
        ai_summary += "……"
    avoid_hint = ""
    if existing_titles:
        recent = existing_titles[-50:]
        avoid_hint = (
            f"\n【已有的会话标题（必须避免）】\n{', '.join(recent)}\n"
        )
    prompt = f"""你是一位标题提炼专家。请根据以下完整对话，生成两个标题：

1. **会话标题**（5~8个字）：概括整段对话的核心主题，必须区别于【已有的会话标题】列表。
2. **本轮标题**（4~6个字）：精准概括用户这一轮提问的独特意图，用于会话内的快速导航。

用户问题：
{user_msg[:200]}

AI回答摘要：
{ai_summary}

{avoid_hint}
要求：
- 标题必须基于具体内容，禁止使用“对话”、“咨询”、“讨论”、“学习”等泛化词汇。
- 如果涉及领域（如编程、管理、心理），请在标题中体现。
- 会话标题要确保与已有列表完全不同（如内容相似，请加场景/时间后缀）。
- 本轮标题要突出本轮提问的独特侧重点。

只返回 JSON，格式：{{"session_title": "...", "round_title": "..."}}
"""
    try:
        ai = api_key_factory()
        result = ai.chat_json(prompt, temperature=0.6)
        if "error" not in result:
            sess_title = result.get("session_title", "").strip()
            round_title = result.get("round_title", "").strip()
            if sess_title:
                original = sess_title
                counter = 2
                title_set = set(existing_titles)
                while sess_title in title_set:
                    sess_title = f"{original} ({counter})"
                    counter += 1
                    if len(sess_title) > 15:
                        sess_title = sess_title[:12] + "..."
            return sess_title, round_title
    except Exception as e:
        if log:
            log(f"⚠️ AI 生成双标题失败: {e}")
    return "", ""

def generate_round_label_simple(
    user_msg: str,
    api_key_factory: Any,
    existing_labels: List[str],
    log: Any = None,
) -> str:
    """生成 4~6 字本轮标题，并在已有标签中做简单去重。"""
    if not user_msg:
        return ""
    prompt = f"""请根据以下本轮提问，生成一个 4~6 字的精炼标题（仅输出标题，不要其他内容）：

用户问题：{user_msg[:150]}

标题要求：精准概括本轮提问的核心意图，避免泛化词汇。
只输出标题，不加引号或其他格式。
"""
    try:
        ai = api_key_factory()
        title = ai.chat(prompt, temperature=0.5)
        title = title.strip().strip('"').strip("'")
        matching = [lbl for lbl in existing_labels if lbl and lbl.startswith(title[:3])]
        if matching:
            counter = 2
            orig = title
            while any(lbl == title for lbl in matching):
                title = f"{orig} ({counter})"
                counter += 1
                if len(title) > 10:
                    title = title[:8] + "…"
        return title
    except Exception as e:
        if log:
            log(f"⚠️ 轮次标题生成失败: {e}")
        return ""

def build_elegant_narrative_prompt(
    one_sentence: str,
    student_answer: str,
) -> str:
    """构建儒雅风格叙事的 Prompt。"""
    return f"""
请将以下商业分析内容，改写为一段「儒雅风格」的文字。

【核心观点】
{one_sentence}

【详细建议】
{student_answer[:600] if student_answer else "（无）"}

【风格要求】
模仿苏轼的旷达通透与辛弃疾的豪迈沉郁——文字从容而有筋骨，既有"一蓑烟雨任平生"的豁达，又有"把吴钩看了，栏杆拍遍"的深沉关怀。

【具体要求】
1. 以"以我观之，此事有三层意味"或类似文人开篇起笔
2. 中间穿插一个自然意象（如山、水、月、竹、云），借景说理
3. 引用一句古诗词或化用其意境（可改动以适应语境）
4. 结尾落在"行"字上——不是空谈，是可行之道
5. 字数：100-150字（精简隽永，点到即止）
6. 通篇让人感觉像在品茶听琴时的一席话，不急切、不炫耀

【输出要求】
只输出正文，不加标题、不加序号、不加任何格式标记（如 Markdown）。
"""

def generate_elegant_narrative(
    ai: Any,
    one_sentence: str,
    student_answer: str,
    return_only: bool = True,
) -> Optional[str]:
    """生成儒雅叙事纯文本；return_only=False 时返回 Prompt 供 UI 流式使用。"""
    if not one_sentence and not student_answer:
        return None
    prompt = build_elegant_narrative_prompt(one_sentence, student_answer)
    if not return_only:
        return prompt
    try:
        full_text = ai.chat(
            prompt,
            system=(
                "你是一位深谙苏轼、辛弃疾文风的散文大家。"
                "你写的文字让人读来如沐春风，心中舒畅。你只输出正文。"
            ),
        )
        return full_text.strip()
    except Exception:
        return (
            f"以我观之，此事如月照寒潭，明澈而深邃。{one_sentence}。"
            "行者自知，行之者自达。"
        )

def run_single_deep_reasoning(
    engine: Any,
    ai: Any,
    api_key: str,
    user_input: str,
    context_builder: Any,
    on_progress: Any,
) -> str:
    """单路径深度推理：裸模型、晶体评论、综合融合。"""
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key
    full_input = context_builder(user_input)
    on_progress(30, "裸模型生成中")
    raw = ai.chat(
        full_input,
        system="请直接回答问题，不要引用外部知识，给出最直接的答案。",
    )
    assoc_crystals = engine.get_associative_crystals(user_input, top_k=5)
    if assoc_crystals:
        crystal_ctx = "\n".join([f"- [{c.id}] {c.content}" for c in assoc_crystals])
        on_progress(60, "晶体树评论中")
        comment_prompt = (
            f"用户问题：{user_input}\n裸模型回答：{raw}\n"
            f"相关晶体树知识（联想检索）：\n{crystal_ctx}\n"
            "请指出哪些晶体支持或反驳了裸模型回答，以及提供了哪些新视角。"
        )
        comment = ai.chat(comment_prompt, system="你是晶体树的知识审计员，输出晶体观点。")
    else:
        comment = "（无相关晶体）"

    on_progress(80, "综合融合中")
    final_prompt = (
        f"原始问题：{user_input}\n裸模型回答：{raw}\n晶体树评论：{comment}\n"
        "请综合两者给出最终答案，并说明裸模型和晶体树各自的贡献。"
    )
    final = ai.chat(final_prompt, system="你是认知晶体树的综合推理者，输出最终答案。")
    result = (
        f"【裸模型回答】\n{raw}\n\n"
        f"【晶体树评论（联想增强）】\n{comment}\n\n"
        f"【综合最终答案】\n{final}"
    )
    on_progress(100, "完成")
    return reply_with_score(result)

def run_debate_engine_reasoning(
    engine: Any,
    ai: Any,
    api_key: str,
    roles: List[Any],
    user_input: str,
    debate_mode: str,
    max_rounds: int,
    rumad_enabled: bool,
    context_builder: Any,
    fingerprint_getter: Any,
    on_progress: Any,
    on_log: Any,
) -> tuple:
    """运行 DebateEngine 并返回结果与实例，UI 渲染留在 access。"""
    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key

    def thread_safe_log(message, level="system"):
        on_log(message, level)

    if debate_mode == "twin_self_play":
        fingerprint = fingerprint_getter()
        if fingerprint and fingerprint.confidence > 0.3:
            on_log(
                f"[INFO] 加载认知指纹成功 (置信度={fingerprint.confidence:.2f})",
                "system",
            )
            debate = DebateEngine(
                ai,
                engine,
                roles,
                thread_safe_log,
                progress_callback=on_progress,
            )
            debate.roles = debate.get_roles_with_twin(
                include_twin=True,
                fingerprint=fingerprint,
            )
            debate_mode_effective = "debate_full"
        else:
            on_log("[WARN] 认知指纹不足，使用标准多角色辩论", "warning")
            debate = DebateEngine(
                ai,
                engine,
                roles,
                thread_safe_log,
                progress_callback=on_progress,
            )
            debate_mode_effective = debate_mode
    else:
        debate = DebateEngine(
            ai,
            engine,
            roles,
            thread_safe_log,
            progress_callback=on_progress,
        )
        debate_mode_effective = debate_mode

    if rumad_enabled:
        debate.rumad_enabled = True
        debate.rumad.set_enabled(True)
        on_log("🧠 RUMAD 拓扑控制已通过 GUI 启用", "system")
    else:
        debate.rumad_enabled = False
        debate.rumad.set_enabled(False)
        on_log("🧠 RUMAD 拓扑控制已禁用", "system")

    assert isinstance(debate, DebateEngine), f"debate 类型异常: {type(debate)}"
    reason_input = context_builder(user_input, limit=20)
    result = debate.run(
        reason_input,
        mode=debate_mode_effective,
        max_rounds=max_rounds,
    )
    if isinstance(result, dict):
        attach_debate_score(result)
    return result, debate

def is_complex_question(question: str) -> bool:
    """判断问题是否属于需要深度推理的复杂问题。"""
    keywords = [
        "如何",
        "为什么",
        "方案",
        "决策",
        "分析",
        "比较",
        "评估",
        "设计",
        "策略",
        "方法",
        "框架",
    ]
    has_keyword = any(kw in question for kw in keywords)
    hole_keywords = [
        "非共识",
        "高不确定性",
        "复杂系统",
        "多重约束",
        "因果",
        "判断",
        "决策",
        "H001",
        "H002",
        "H003",
    ]
    has_hole_keyword = any(kw in question for kw in hole_keywords)
    return (len(question) > 20 and has_keyword) or has_hole_keyword
