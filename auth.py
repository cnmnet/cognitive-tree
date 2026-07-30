# auth.py
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ---------- 路径配置 ----------
BASE_DIR = Path(__file__).resolve().parent   # 当前文件所在目录（项目根）
USER_DB_FILE = str(BASE_DIR / "晶体树文件夹" / "系统日志" / "users.json")

# 配置文件（可考虑从 config.py 导入，这里简单定义）
SECRET_KEY = "your-very-secret-key-change-in-production"  # 应从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

class User(BaseModel):
    username: str
    password_hash: str
    tier: str = "free"          # free / pro
    trial_used: int = 0
    max_trials: int = 20
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
            return {u: User(**v) for u, v in data.items()}
    except:
        return {}

def _save_users(users: Dict[str, User]):
    # 确保目录存在
    Path(USER_DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(USER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({u: v.dict() for u, v in users.items()}, f, ensure_ascii=False, indent=2)

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
    except jwt.PyJWTError:
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
    return users.get(username)

def update_user_tier(username: str, new_tier: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    users[username].tier = new_tier
    users[username].updated_at = datetime.now().isoformat()
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

def get_trial_remaining(username: str) -> int:
    users = _load_users()
    user = users.get(username)
    if not user:
        return 0
    if user.tier == "pro":
        return 9999
    return max(0, user.max_trials - user.trial_used)

# ---------- FastAPI 依赖注入 ----------
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="无效的令牌")
    username = payload["sub"]
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

# 付费门控：检查用户是否有权限使用付费功能
def require_tier(tier_required: str = "pro"):
    async def dependency(user: User = get_current_user):
        if user.tier != tier_required:
            remaining = get_trial_remaining(user.username)
            if user.tier == "free" and remaining > 0:
                # 允许试用，但消耗一次试用次数
                increment_trial(user.username)
                return user
            raise HTTPException(status_code=403, detail=f"需要 {tier_required} 订阅或剩余试用次数不足")
        return user
    return dependency