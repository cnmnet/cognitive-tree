# auth.py
import base64
import json
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ---------- 路径配置 ----------
BASE_DIR = Path(__file__).resolve().parent   # 当前文件所在目录（项目根）
USER_DB_FILE = str(BASE_DIR / "晶体树文件夹" / "系统日志" / "users.json")

# 配置文件（可考虑从 config.py 导入，这里简单定义）
SECRET_KEY = "your-very-secret-key-change-in-production"  # 应从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

_CRYPTO_KEY: Optional[bytes] = None


def _get_crypto_key() -> bytes:
    global _CRYPTO_KEY
    if _CRYPTO_KEY is not None:
        return _CRYPTO_KEY
    secret = os.getenv("CRYSTAL_TREE_KEY_SECRET", "")
    if secret:
        try:
            key = bytes.fromhex(secret)
        except ValueError:
            raise RuntimeError("CRYSTAL_TREE_KEY_SECRET 必须是合法的 hex 字符串")
        if len(key) != 32:
            raise RuntimeError("CRYSTAL_TREE_KEY_SECRET 必须是 32 字节的 hex 字符串")
    else:
        key_file = BASE_DIR / "security.key"
        if key_file.exists():
            key = key_file.read_bytes()
        else:
            key = os.urandom(32)
            key_file.write_bytes(key)
        if len(key) != 32:
            raise RuntimeError("security.key 长度错误")
    _CRYPTO_KEY = key
    return key


def encrypt_secret(plain: str) -> str:
    aesgcm = AESGCM(_get_crypto_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plain.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    raw = base64.b64decode(token)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_get_crypto_key())
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def mask_secret(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 10:
        return key[:3] + "****"
    return key[:6] + "****" + key[-4:]

class User(BaseModel):
    username: str
    password_hash: str
    api_key_encrypted: str = ""  # AES-GCM 加密后的 DeepSeek API Key
    api_key_updated_at: str = ""
    tier: str = "free"          # free / pro
    trial_used: int = 0         # 保留旧字段，但不再用于专业版
    max_trials: int = 20        # 保留旧字段
    monthly_used: int = 0       # 本月已用次数（仅专业版）
    month_reset_date: str = ""  # 上次重置的月份，如 "2026-08"
    created_at: str = ""
    updated_at: str = ""

class TokenData(BaseModel):
    username: str
    tier: str

def _load_users() -> Dict[str, User]:
    # 确保目录存在
    Path(USER_DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(USER_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            users = {}
            migrated = False
            for u, v in data.items():
                user = User(**v)
                old_key = v.get("api_key", "")
                if old_key and not user.api_key_encrypted:
                    user.api_key_encrypted = encrypt_secret(old_key)
                    user.api_key_updated_at = datetime.now().isoformat()
                    migrated = True
                users[u] = user
            if migrated:
                _save_users(users)
            return users
    except:
        return {}

def _save_users(users: Dict[str, User]):
    # 确保目录存在
    Path(USER_DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(USER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({u: v.model_dump() for u, v in users.items()}, f, ensure_ascii=False, indent=2)

def hash_password(password: str) -> str:
    salt = "crystal_salt"  # 固定盐（实际应随机）
    return hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(password: str, hash_val: str) -> bool:
    return hash_password(password) == hash_val

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as e:
        print(f"[WARN] Token 解码失败: {e}")
        return {}

# ---------- 业务函数 ----------
def register_user(username: str, password: str) -> Tuple[bool, str]:
    users = _load_users()
    if username in users:
        return False, "用户名已存在"
    user = User(
        username=username,
        password_hash=hash_password(password),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    users[username] = user
    _save_users(users)
    return True, "注册成功"

def login_user(username: str, password: str) -> Tuple[bool, str, Optional[str]]:
    users = _load_users()
    user = users.get(username)
    if not user:
        return False, "用户不存在", None
    if not verify_password(password, user.password_hash):
        return False, "密码错误", None
    token = create_access_token({"sub": username, "tier": user.tier})
    return True, "登录成功", token

def get_user(username: str) -> Optional[User]:
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    # ★★★ 确保新字段有默认值 ★★★
    if not hasattr(user, 'monthly_used'):
        user.monthly_used = 0
    if not hasattr(user, 'month_reset_date'):
        user.month_reset_date = ""
    return user

def set_user_api_key(username: str, api_key: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    users[username].api_key_encrypted = encrypt_secret((api_key or "").strip())
    users[username].api_key_updated_at = datetime.now().isoformat()
    _save_users(users)
    return True

def get_user_api_key(username: str) -> str:
    user = get_user(username)
    if not user or not user.api_key_encrypted:
        return ""
    try:
        return decrypt_secret(user.api_key_encrypted)
    except Exception:
        return ""

def clear_user_api_key(username: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    users[username].api_key_encrypted = ""
    users[username].api_key_updated_at = ""
    _save_users(users)
    return True

def get_user_api_key_masked(username: str) -> str:
    return mask_secret(get_user_api_key(username))

def delete_user(username: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    del users[username]
    _save_users(users)
    return True

def update_user_tier(username: str, new_tier: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    user = users[username]
    user.tier = new_tier
    user.updated_at = datetime.now().isoformat()
    # 如果是升级到专业版，重置月度数据
    if new_tier == "pro":
        user.monthly_used = 0
        user.month_reset_date = datetime.now().strftime("%Y-%m")
    users[username] = user
    _save_users(users)
    return True

def increment_trial(username: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    user = users[username]
    if user.tier == "pro":
        return True  # 无限制
    if user.trial_used >= user.max_trials:
        return False
    user.trial_used += 1
    user.updated_at = datetime.now().isoformat()
    _save_users(users)
    return True

def get_remaining_quota(username: str) -> int:
    """返回用户当前可用的免费调用次数。若用户为 free 且未设置 Key，返回 0；若为 pro，返回月度剩余次数。"""
    users = _load_users()
    user = users.get(username)
    if not user:
        return 0
    # 如果是 pro，检查月度额度
    if user.tier == "pro":
        # 重置月度计数（如果月份变化）
        reset_monthly_usage_if_needed(username)
        # 重新读取用户数据（因为可能已更新）
        user = users.get(username)
        return max(0, user.max_trials - user.monthly_used)
    # free 用户不提供免费额度（只能自备 Key）
    return 0

def reset_monthly_usage_if_needed(username: str):
    """如果当前月份与记录的月份不同，将 monthly_used 重置为 0。"""
    users = _load_users()
    user = users.get(username)
    if not user or user.tier != "pro":
        return
    current_month = datetime.now().strftime("%Y-%m")
    if user.month_reset_date != current_month:
        user.monthly_used = 0
        user.month_reset_date = current_month
        users[username] = user
        _save_users(users)

def consume_monthly_quota(username: str) -> bool:
    """消耗一次月度额度，返回是否成功（剩余次数>0）。"""
    users = _load_users()
    user = users.get(username)
    if not user or user.tier != "pro":
        return False
    reset_monthly_usage_if_needed(username)
    # 重新加载用户
    users = _load_users()
    user = users.get(username)
    if user.monthly_used < user.max_trials:
        user.monthly_used += 1
        user.updated_at = datetime.now().isoformat()
        users[username] = user
        _save_users(users)
        return True
    return False

# ---------- FastAPI 依赖注入 ----------
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if not payload or "sub" not in payload:
            raise HTTPException(status_code=401, detail="无效的令牌")
        username = payload["sub"]
        user = get_user(username)
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    except Exception as e:
        print(f"[ERROR] get_current_user 异常: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=401, detail=f"认证失败: {str(e)}")

# 付费门控：检查用户是否有权限使用付费功能
def require_tier(tier_required: str = "pro"):
    async def dependency(user: User = get_current_user):
        if user.tier != tier_required:
            remaining = get_remaining_quota(user.username)
            if user.tier == "free" and remaining > 0:
                # 允许试用，但消耗一次试用次数
                increment_trial(user.username)
                return user
            raise HTTPException(status_code=403, detail=f"需要 {tier_required} 订阅或剩余试用次数不足")
        return user
    return dependency

def get_trial_remaining(username: str) -> int:
    """返回用户当前可用的免费调用次数。"""
    users = _load_users()
    user = users.get(username)
    if not user:
        return 0
    if user.tier == "pro":
        # 对于专业版，返回月度剩余次数
        reset_monthly_usage_if_needed(username)
        # 重新加载用户，因为可能已更新
        users = _load_users()
        user = users.get(username)
        if user:
            return max(0, user.max_trials - user.monthly_used)
        return 0
    # 免费版用户：返回 0，提示需设置 API Key
    return 0
