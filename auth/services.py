"""用户/API Key 相关服务：作为 auth 模块的伴生服务层。"""

from __future__ import annotations

from typing import Any, Dict


def register_user(auth: Any, username: str, password: str) -> Dict[str, Any]:
    success, msg = auth.register_user(username, password)
    if not success:
        raise ValueError(msg)
    return {"ok": True, "message": msg}


def login_user(auth: Any, username: str, password: str) -> Dict[str, Any]:
    success, msg, token = auth.login_user(username, password)
    if not success:
        raise ValueError(msg)
    return {"ok": True, "message": msg, "token": token}


def current_user_info(auth: Any, user: Any) -> Dict[str, Any]:
    return {
        "username": user.username,
        "tier": user.tier,
        "trial_used": user.trial_used,
        "trial_remaining": auth.get_trial_remaining(user.username),
        "api_key_configured": bool(auth.get_user_api_key(user.username)),
        "api_key_masked": auth.get_user_api_key_masked(user.username),
    }


def update_user_api_key(
    auth: Any,
    ai_client_factory: Any,
    username: str,
    api_key: str,
) -> Dict[str, Any]:
    key = api_key.strip()
    if not key.startswith("sk-") or len(key) < 20:
        raise ValueError("API Key 格式不正确")
    probe = ai_client_factory(api_key=key).chat(
        "回复OK",
        temperature=0,
        max_tokens=5,
    )
    if (
        not isinstance(probe, str)
        or probe.startswith("错误")
        or probe.startswith("AI调用失败")
    ):
        raise ValueError("API Key 无效或已过期")
    auth.set_user_api_key(username, key)
    return {"ok": True, "api_key_masked": auth.mask_secret(key)}


def clear_user_api_key(auth: Any, username: str) -> Dict[str, Any]:
    auth.clear_user_api_key(username)
    return {"ok": True, "api_key_configured": False}


def delete_user_account(auth: Any, user: Any, password: str) -> Dict[str, Any]:
    if not auth.verify_password(password, user.password_hash):
        raise ValueError("密码错误")
    auth.delete_user(user.username)
    return {"ok": True, "message": "账号已删除"}


def privacy_content(project_root: Any) -> Dict[str, Any]:
    privacy_file = project_root / "docs" / "隐私说明.md"
    if privacy_file.exists():
        return {"content": privacy_file.read_text(encoding="utf-8")}
    return {"content": "（隐私说明未发布）"}


def check_ai_access(auth: Any, user: Any, api_key: str) -> tuple:
    key = (api_key or "").strip() or auth.get_user_api_key(user.username)
    if key:
        return True, "使用用户 API Key", key
    return False, "请先在设置中保存自己的 DeepSeek API Key", ""


def user_effective_key(auth: Any, user: Any, payload_key: str = "") -> str:
    key = (payload_key or "").strip() or auth.get_user_api_key(user.username)
    if not key:
        raise ValueError("请先设置自己的 DeepSeek API Key")
    return key
