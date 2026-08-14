"""数据层服务：会话读写与历史数据恢复。"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List

from core.text_utils import normalize_text


def list_sessions(db: Any) -> List[Dict[str, Any]]:
    """列出有效会话，隐藏空的新会话。"""
    result = []
    for sid, name, updated in db.list_sessions():
        if name.startswith("新会话"):
            _name, history, _ = db.get_session(sid)
            if not history:
                continue
        result.append({"id": sid, "name": name, "updated_at": updated})
    return result


def visible_sessions(db: Any, sessions: List[Any], search: str = "") -> List[Any]:
    """过滤会话列表：按名称搜索，并隐藏空的新会话。"""
    search = (search or "").strip().lower()
    result = []
    for sid, name, _updated in sessions:
        if search and search not in str(name).lower():
            continue
        try:
            _sname, history, _ = db.get_session(sid)
            if not history and str(name).startswith("新会话"):
                continue
        except Exception:
            continue
        result.append((sid, name))
    return result


def ensure_session(db: Any, session_id: str = "") -> str:
    """返回已有会话或创建新会话。"""
    if session_id:
        name, _, _ = db.get_session(session_id)
        if name is not None:
            return session_id
    sid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]
    db.create_session(sid, f"新会话 {datetime.now().strftime('%H:%M')}")
    return sid


def add_session_message(
    db: Any,
    session_id: str,
    role: str,
    content: str,
    title_generator: Any = None,
) -> None:
    """向会话追加消息，首条用户消息自动生成标题。"""
    name, history, _ = db.get_session(session_id)
    if name is None:
        raise ValueError("会话不存在")
    history.append((role, content))
    if role == "user" and len(history) == 1 and name.startswith("新会话"):
        new_name = title_generator(content) if title_generator else ""
        if new_name:
            db.rename_session(session_id, new_name)
            name = new_name
    db.update_session(session_id, history, name)


def history_context(
    db: Any,
    session_id: str,
    current_input: str,
    limit: int = 8,
) -> str:
    """组装最近会话上下文。"""
    _name, history, _ = db.get_session(session_id)
    lines = []
    for role, content in history[-limit:]:
        if role == "user" and current_input and current_input in content:
            continue
        label = "用户" if role == "user" else "AI"
        text = normalize_text(content, 900)
        if text:
            lines.append(f"{label}: {text}")
    if not lines:
        return current_input
    return "【本会话最近上下文】\n" + "\n".join(lines) + f"\n\n【当前问题】\n{current_input}"


def question_history(history: List[Any]) -> List[Dict[str, Any]]:
    """从会话历史中提取用户问题列表。"""
    result = []
    q_num = 1
    for index, (role, content) in enumerate(history):
        if role != "user":
            continue
        label = content
        for prefix, name in [
            ("[晶体化] ", "[晶体化] "),
            ("[深度推理] ", "[深度推理] "),
            ("[深度推理-多角色] ", "[多角色] "),
            ("[文件内容] ", "[文件] "),
        ]:
            if content.startswith(prefix):
                label = name + content[len(prefix):]
                break
        result.append(
            {
                "index": index,
                "label": f"{q_num}. {label[:52]}{'...' if len(label) > 52 else ''}",
                "content": content,
            }
        )
        q_num += 1
    return result


def update_last_round_label(db: Any, session_id: str, label: str) -> None:
    """把会话最后一条用户消息的轮次标题写入 labels。"""
    name, history, labels = db.get_session(session_id)
    if not history:
        return
    last_user_idx = -1
    for i in range(len(history) - 1, -1, -1):
        if history[i][0] == "user":
            last_user_idx = i
            break
    if last_user_idx == -1:
        return
    new_messages = []
    for i, (role, content) in enumerate(history):
        lbl = labels[i] if i < len(labels) else None
        if i == last_user_idx:
            lbl = label
        new_messages.append({"role": role, "content": content, "label": lbl})
    db.update_session(session_id, new_messages, name)


def create_session_record(db: Any, name: str = "") -> Dict[str, str]:
    sid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]
    name = name or f"新会话 {datetime.now().strftime('%H:%M')}"
    db.create_session(sid, name)
    return {"id": sid, "name": name}


def get_session_record(db: Any, session_id: str) -> Dict[str, Any]:
    name, history, labels = db.get_session(session_id)
    if name is None:
        raise ValueError("会话不存在")
    return {
        "id": session_id,
        "name": name,
        "messages": [{"role": r, "content": c} for r, c in history],
        "questions": question_history(history),
    }


def rename_session_record(db: Any, session_id: str, name: str) -> None:
    db.rename_session(session_id, name.strip())


def delete_session_record(db: Any, session_id: str) -> None:
    db.delete_session(session_id)


def clear_session_record(db: Any, session_id: str) -> None:
    name, _, _ = db.get_session(session_id)
    if name is None:
        raise ValueError("会话不存在")
    db.update_session(session_id, [], name)


def restore_original_sessions(
    config: Any,
    candidates: List[Any],
    log: Any,
) -> bool:
    """从历史项目复制数据目录与会话库，只复制不删除。"""
    current = config.DATA_ROOT
    if not current.is_dir():
        return False
    for cand in candidates:
        if cand.resolve() == current.resolve():
            continue
        copied = False
        for name in ("晶体数据", "核心配置", "系统日志", "暂存区", "skills", "model_cache"):
            src = cand / name
            if src.is_dir():
                shutil.copytree(src, current / name, dirs_exist_ok=True)
                copied = True
        src_db = cand / "chat_sessions.db"
        if src_db.is_file():
            shutil.copy2(src_db, current / "chat_sessions.db")
            copied = True
        if copied:
            log("✅ 已从原项目复制历史数据到当前数据库", "success")
            return True
    return False
