#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth
from auth import User, get_current_user
from access.dependencies import (
    AIClient,
    BatchProcessor,
    Config,
    DailyPlanner,
    DebateEngine,
    ExternalFetcher,
    HealthChecker,
    SearchService,
    generate_session_title_from_content,
)
import stripe
import webhook
from auth.services import (
    check_ai_access as check_ai_access_service,
    clear_user_api_key,
    current_user_info,
    delete_user_account,
    login_user,
    privacy_content,
    register_user,
    update_user_api_key,
    user_effective_key,
)
from governance.i18n import tr
from data.services import (
    add_session_message as append_session_message,
    clear_session_record as clear_session_data,
    create_session_record as add_session_record,
    delete_session_record as delete_session_data,
    ensure_session as ensure_session_id,
    get_session_record as load_session_record,
    history_context as build_history_context,
    list_sessions as session_list,
    rename_session_record as rename_session_data,
)
from external.services import (
    get_conflicts as load_conflicts,
    get_radar as load_radar,
    get_trending as load_trending,
    refresh_trending as refresh_trending_data,
    search_documents,
    sync_vector_store as run_vector_sync,
    vector_status as get_vector_status,
)
from governance.services import load_roles
from harness.services import (
    assets as build_assets_snapshot,
    build_crystallization_prompt,
    confirm_pending_card,
    delete_asset as remove_asset,
    existing_crystal_ids,
    get_fingerprint as get_fingerprint_snapshot,
    get_hebbian_stats,
    get_skill as load_skill,
    health_dashboard as build_health_dashboard,
    holes_snapshot,
    ignore_pending_card,
    ignore_task as mark_task_ignored,
    list_skills as skill_list,
    normalize_crystal_response,
    patch_asset as update_asset,
    pending_cards,
    resolve_task as mark_task_done,
    run_batch_process_task,
    run_chat_task,
    run_crystallize_task,
    run_daily_plan_task,
    run_deep_reasoning_task,
    run_file_chat_task,
    run_skill_migration,
    submit_hebbian_reward as record_hebbian_reward,
    system_health,
    system_status,
    task_cards,
    today_snapshot,
    update_files,
    validate_single_skill as validate_one_skill,
    validate_skills as validate_skills_batch,
)
from harness.session_jobs import JobManager
from webhook.services import create_checkout_session as build_checkout_session
from access.factory import create_web_backend
from access.web_services import LegacyProcessManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _user_effective_key(user: User, payload_key: str = "") -> str:
    try:
        return user_effective_key(auth, user, payload_key)
    except ValueError:
        raise HTTPException(status_code=403, detail=tr("need_api_key"))

WEB_ROOT = PROJECT_ROOT / "web_static"
job_manager = JobManager()
legacy_process_manager = LegacyProcessManager()

_backend = create_web_backend()
db = _backend["db"]
files = _backend["files"]
ai_client = _backend["ai_client"]
engine = _backend["engine"]

app = FastAPI(title="认知晶体树 5 Web", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    #allow_origins=["http://127.0.0.1:8788", "http://localhost:8788"],
    allow_origins=["*"],   # 允许任何来源，仅开发测试用
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(WEB_ROOT)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#6f56d9"/>'
        '<text x="16" y="23" font-size="18" text-anchor="middle" fill="#fff" '
        'font-family="sans-serif">晶</text></svg>'
    )
    return Response(content=svg, media_type="image/svg+xml")


# ===== 应用启动事件：初始化审计服务 =====
@app.on_event("startup")
async def startup_event():
    """应用启动时自动初始化审计服务，生成健康度数据"""
    print("[INFO] initializing audit service...")
    try:
        # 启动后台审计服务
        engine.start_audit_service()
        # 立即运行一次审计，生成健康数据
        engine.run_audit_now()
        print("[OK] audit service started; health data generated")
    except Exception as e:
        print(f"[WARN] audit service startup failed: {e}")

# 认证中间件（保护 /api/* 但排除 /api/auth/* 和 /api/webhook）

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 放行路径
    public_paths = ["/api/auth/login", "/api/auth/register", "/api/webhook", "/", "/static", "/api/health", "/api/status"]
    if any(request.url.path.startswith(p) for p in public_paths):
        return await call_next(request)
    # 检查 token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response("未授权", status_code=401)
    token = auth_header[7:]
    payload = auth.decode_token(token)
    if not payload or "sub" not in payload:
        return Response("无效令牌", status_code=401)
    # 将用户信息存入 request.state 供后续使用
    request.state.user = payload.get("sub")
    request.state.tier = payload.get("tier", "free")
    return await call_next(request)

# 路由
@app.get("/")
def index():
    return FileResponse(WEB_ROOT / "index.html")

@app.get("/api/bootstrap")
def bootstrap():
    assets = build_assets_snapshot(engine)
    return {
        "data_root": str(Config.DATA_ROOT),
        "db_path": str(Config.get_db_path()),
        "api_key_configured": bool(Config.get_api_key()),
        "sessions": session_list(db),
        "assets": assets["counts"],
        "pending_count": len(pending_cards(files)),
        "task_count": len([t for t in task_cards(files) if t.get("status") == "pending"]),
        "legacy_backend_running": legacy_process_manager.is_running(),
    }

@app.post("/api/vector/sync")
def sync_vector_store():
    """同步向量库（将当前所有晶体向量化）"""
    return run_vector_sync(engine)

@app.post("/api/payment/create-checkout")
async def create_checkout_session(user: auth.User = Depends(auth.get_current_user)):
    try:
        return build_checkout_session(Config, stripe, user.username)
    except ValueError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(400, f"创建支付会话失败: {str(e)}")                                                  
@app.post("/api/webhook")
async def payment_webhook(request: Request):
    return await webhook.handle_payment_webhook(request)

# ===== Day 20: GitHub Trending API & 全球认知雷达 =====

print("[OK] registered /api/trending route")
@app.get("/api/trending")
def get_trending(limit: int = 10):
    """获取已保存的 GitHub Trending 晶体"""
    return load_trending(engine, limit)

print("[OK] registered /api/trending/refresh route")
@app.post("/api/trending/refresh")
def refresh_trending(max_items: int = 10):
    """手动刷新 GitHub Trending：抓取最新热门仓库并生成晶体"""
    return refresh_trending_data(engine, max_items)

print("[OK] registered /api/radar route")
@app.get("/api/radar")
def get_radar():
    """获取全球认知雷达数据（多语言新闻）"""
    return load_radar(ExternalFetcher)
@app.get("/api/vector/status")
def vector_status():
    """获取向量库状态"""
    return get_vector_status(engine)

@app.get("/api/conflicts")
def get_conflicts(method: str = "auto", limit: int = 20):
    """获取检测到的晶体冲突"""
    return load_conflicts(engine, method, limit)


class AuthRegister(BaseModel):
    username: str
    password: str

class AuthLogin(BaseModel):
    username: str
    password: str

@app.post("/api/auth/register")
async def register(payload: AuthRegister):
    try:
        return register_user(auth, payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
async def login(payload: AuthLogin):
    try:
        return login_user(auth, payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/api/auth/me")
async def me(user: auth.User = Depends(auth.get_current_user)):
    return current_user_info(auth, user)


class ApiKeyRequest(BaseModel):
    api_key: str


@app.put("/api/auth/key")
async def update_api_key(payload: ApiKeyRequest, user: auth.User = Depends(auth.get_current_user)):
    try:
        return update_user_api_key(
            auth,
            AIClient,
            user.username,
            payload.api_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/auth/key")
async def delete_api_key(user: auth.User = Depends(auth.get_current_user)):
    return clear_user_api_key(auth, user.username)


class AccountDeleteRequest(BaseModel):
    password: str


@app.delete("/api/auth/account")
async def delete_account(payload: AccountDeleteRequest, user: auth.User = Depends(auth.get_current_user)):
    try:
        return delete_user_account(auth, user, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/privacy")
async def privacy():
    return privacy_content(PROJECT_ROOT)

# ===== Day 9: Skill 管理 API =====

class SkillValidateRequest(BaseModel):
    crystal_ids: List[str] = Field(default_factory=list)

@app.get("/api/skills")
def list_skills():
    """获取所有可用的 Skill ID"""
    return skill_list(engine)

@app.get("/api/skills/{crystal_id}")
def get_skill(crystal_id: str):
    """获取单个 Skill 的详细信息"""
    try:
        return load_skill(engine, crystal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/skills/validate")
def validate_skills(payload: SkillValidateRequest):
    """批量验证 Skill"""
    return validate_skills_batch(engine, payload.crystal_ids)

@app.get("/api/skills/{crystal_id}/validate")
def validate_single_skill(crystal_id: str):
    """验证单个 Skill"""
    return validate_one_skill(engine, crystal_id)

@app.post("/api/skills/migrate")
def migrate_to_skills(background: BackgroundTasks):
    """执行晶体到 Skill 的迁移（后台任务）"""
    job_id = job_manager.create("migrate-skills")
    
    def task():
        try:
            run_skill_migration(
                lambda **kwargs: job_manager.set(job_id, **kwargs),
                lambda m, level="system": job_manager.log(job_id, m, level),
            )
        except Exception as e:
            job_manager.set(job_id, status="error", error=str(e))
            job_manager.log(job_id, f"迁移失败: {e}", "error")
    
    background.add_task(job_manager.run, job_id, task)
    return {"job_id": job_id}

# Pydantic models
class SessionCreate(BaseModel):
    name: Optional[str] = None

class SessionRename(BaseModel):
    name: str

class ChatRequest(BaseModel):
    session_id: str
    input: str
    api_key: Optional[str] = None

class CrystalRequest(ChatRequest):
    fast_mode: bool = True
    scope: str = "全局"

class DeepReasonRequest(ChatRequest):
    mode: str = "multi_role"
    max_rounds: int = 2

class BatchRequest(BaseModel):
    folder: str
    mode: str = "chat"
    fast_mode: bool = True
    inject_history: bool = False
    session_id: Optional[str] = None
    api_key: Optional[str] = None

class DailyPlanRequest(BaseModel):
    api_key: Optional[str] = None
    intent_keywords: List[str] = Field(default_factory=list)
    time_budget_seconds: int = 900

class SearchRequest(BaseModel):
    keyword: str
    regex: bool = False
    dirs: List[str] = Field(default_factory=lambda: ["晶体数据", "核心配置", "系统日志", "暂存区"])

class CommitRequest(BaseModel):
    session_id: Optional[str] = None
    result: Dict[str, Any]


class HebbianRewardRequest(BaseModel):
    kind: str = "adopt"
    crystal_ids: List[str] = []
    role_keys: List[str] = []
    reward: Optional[float] = None
    question: Optional[str] = None
    task_type: Optional[str] = None


class PendingConfirmRequest(BaseModel):
    content: str
    force: bool = False

class AssetPatchRequest(BaseModel):
    layer: Optional[str] = None
    fixed: Optional[bool] = None

class BackendLoginRequest(BaseModel):
    username: str
    password: str


@app.get("/api/backend/status")
def backend_status():
    return {"running": legacy_process_manager.is_running()}

@app.post("/api/backend/login")
def backend_login(payload: BackendLoginRequest):
    try:
        return legacy_process_manager.login(
            payload.username,
            payload.password,
            PROJECT_ROOT,
            Config,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backend/logout")
def backend_logout():
    return legacy_process_manager.logout()

@app.get("/api/sessions")
def list_sessions():
    return {"sessions": session_list(db)}

@app.post("/api/sessions")
def create_session(payload: SessionCreate):
    return add_session_record(db, payload.name)

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return load_session_record(db, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="会话不存在")

@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, payload: SessionRename):
    rename_session_data(db, session_id, payload.name)
    return {"ok": True}

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    delete_session_data(db, session_id)
    return {"ok": True}

@app.post("/api/sessions/{session_id}/clear")
def clear_session(session_id: str):
    try:
        clear_session_data(db, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}

@app.post("/api/chat")
async def chat(payload: ChatRequest, background: BackgroundTasks, user: User = Depends(get_current_user)):
    allowed, msg, effective_key = check_ai_access_service(auth, user, payload.api_key)
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)
    session_id = ensure_session_id(db, payload.session_id or "")
    try:
        append_session_message(
            db,
            session_id,
            "user",
            payload.input,
            generate_session_title_from_content,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    job_id = job_manager.create("chat")

    def task():
        return run_chat_task(
            db,
            engine,
            AIClient,
            session_id,
            effective_key,
            lambda m: job_manager.log(job_id, m),
        )

    background.add_task(job_manager.run, job_id, task)
    return {"job_id": job_id, "session_id": session_id}

@app.post("/api/crystallize")
async def crystallize(payload: CrystalRequest, background: BackgroundTasks, user: User = Depends(get_current_user)):
    allowed, msg, effective_key = check_ai_access_service(auth, user, payload.api_key)
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)
    session_id = ensure_session_id(db, payload.session_id or "")
    try:
        append_session_message(
            db,
            session_id,
            "user",
            f"[晶体化] {payload.input}",
            generate_session_title_from_content,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    job_id = job_manager.create("crystallize")

    def task():
        return run_crystallize_task(
            db,
            engine,
            AIClient,
            session_id,
            effective_key,
            payload.input,
            payload.fast_mode,
            lambda user_input, search_res: build_crystallization_prompt(
                engine,
                Config,
                existing_crystal_ids(files),
                user_input,
                search_res,
            ),
            lambda ai_response: normalize_crystal_response(
                files,
                engine,
                existing_crystal_ids(files),
                ai_response,
                include_similar=True,
            ),
            lambda m: job_manager.log(job_id, m),
        )

    background.add_task(job_manager.run, job_id, task)
    return {"job_id": job_id, "session_id": session_id}

@app.post("/api/crystallize/commit")
def commit_crystallize(payload: CommitRequest):
    update_files(files, engine, payload.result)
    if payload.session_id:
        try:
            append_session_message(
                db,
                payload.session_id,
                "assistant",
                f"[晶体化结果] {payload.result.get('report_summary', '晶体化完成')}",
                generate_session_title_from_content,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "summary": payload.result.get("report_summary", "晶体化完成")}

@app.post("/api/deep-reasoning")
async def deep_reasoning(
    payload: DeepReasonRequest,
    background: BackgroundTasks,
    user: User = Depends(auth.get_current_user)
):
    allowed, msg, effective_key = check_ai_access_service(auth, user, payload.api_key)
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)
    # ===== Day 21: 试用次数检查 =====
    if user.tier != "pro":
        remaining = auth.get_trial_remaining(user.username)
        if remaining <= 0:
            raise HTTPException(status_code=403, detail="免费试用次数已用完，请升级到专业版")
        auth.increment_trial(user.username)

    # ===== Day 22: 路由层异常捕获 =====
    try:
        session_id = ensure_session_id(db, payload.session_id or "")
        if payload.mode == "lushi_sampling":
            prefix = "[卢氏注意力增强]"
        elif payload.mode in ("debate_light", "debate_full"):
            prefix = "[辩论增强]"
        elif payload.mode == "multi_role":
            prefix = "[深度推理-多角色]"
        else:
            prefix = "[深度推理]"
        try:
            append_session_message(
                db,
                session_id,
                "user",
                f"{prefix} {payload.input}",
                generate_session_title_from_content,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        job_id = job_manager.create("deep-reasoning")

        def task():
            return run_deep_reasoning_task(
                engine,
                AIClient,
                lambda ai, roles, log: DebateEngine(ai, engine, roles, log),
                job_id,
                session_id,
                effective_key,
                payload.mode,
                payload.input,
                payload.max_rounds,
                lambda: load_roles(files),
                lambda sid, current_input, limit=8: build_history_context(
                    db, sid, current_input, limit
                ),
                lambda sid, role, content: append_session_message(
                    db,
                    sid,
                    role,
                    content,
                    generate_session_title_from_content,
                ),
                lambda m, level="system": job_manager.log(job_id, m, level),
            )

        # 提交后台任务
        background.add_task(job_manager.run, job_id, task)
        return {"job_id": job_id, "session_id": session_id}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        job_manager.log(
            job_id if 'job_id' in locals() else 'unknown',
            f"❌ 深度推理路由异常: {e}",
            "error",
        )
        print(f"[ERROR] deep_reasoning 路由异常:\n{error_detail}")
        raise HTTPException(
            status_code=500,
            detail=f"深度推理启动失败: {str(e)}"
        )

@app.post("/api/file-chat")
async def file_chat(
    background: BackgroundTasks,
    session_id: str = Form(...),
    api_key: str = Form(""),
    upload: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    # 权限检查
    allowed, msg, effective_key = check_ai_access_service(auth, user, api_key)
    if not allowed:
        raise HTTPException(status_code=403, detail=msg)

    session_id = ensure_session_id(db, session_id or "")
    job_id = job_manager.create("file-chat")
    upload_dir = Config.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{upload.filename}"
    tmp_path = upload_dir / safe_name
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    def task():
        return run_file_chat_task(
            db,
            AIClient,
            lambda ai, log: BatchProcessor(ai, log),
            session_id,
            effective_key,
            tmp_path,
            upload.filename,
            lambda m, level="system": job_manager.log(job_id, m, level),
        )

    background.add_task(job_manager.run, job_id, task)
    return {"job_id": job_id, "session_id": session_id}

@app.post("/api/batch/start")
def start_batch(payload: BatchRequest, background: BackgroundTasks, user: User = Depends(get_current_user)):
    folder = Path(payload.folder)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="文件夹不存在")
    effective_key = _user_effective_key(user, payload.api_key)
    job_id = job_manager.create("batch")
    stop_event = threading.Event()
    job_manager.stop_flags[job_id] = stop_event

    def task():
        return run_batch_process_task(
            AIClient,
            lambda ai, log: BatchProcessor(ai, log),
            effective_key,
            folder,
            payload.mode,
            payload.fast_mode,
            payload.inject_history,
            payload.session_id or "",
            lambda value: job_manager.set(
                job_id,
                progress=max(5, min(99, int(value))),
            ),
            stop_event.is_set,
            lambda sid, role, content: append_session_message(
                db,
                sid,
                role,
                content,
                generate_session_title_from_content,
            ),
            lambda m, level="system": job_manager.log(job_id, m, level),
        )

    background.add_task(job_manager.run, job_id, task)
    return {"job_id": job_id}

@app.post("/api/batch/stop/{job_id}")
def stop_batch(job_id: str):
    if job_id in job_manager.stop_flags:
        job_manager.stop_flags[job_id].set()
        return {"ok": True}
    raise HTTPException(status_code=404, detail="任务不存在")

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in job_manager.jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job_manager.jobs[job_id]

@app.get("/api/assets")
def assets():
    return build_assets_snapshot(engine)

@app.get("/api/fingerprint")
def get_fingerprint():
    """获取当前认知指纹"""
    return get_fingerprint_snapshot(engine)


@app.post("/api/hebbian/reward")
def submit_hebbian_reward(payload: HebbianRewardRequest, user: auth.User = Depends(auth.get_current_user)):
    """提交 Hebbian 奖励信号：adopt/reject/neutral/activity/quality/reuse/vote。"""
    return record_hebbian_reward(
        engine,
        payload.kind,
        crystal_ids=payload.crystal_ids,
        role_keys=payload.role_keys,
        reward=payload.reward,
        question=payload.question,
        task_type=payload.task_type,
    )


@app.get("/api/hebbian/stats")
def get_hebbian_stats_endpoint(user: auth.User = Depends(auth.get_current_user)):
    """查看 Hebbian 权重状态与参与度统计。"""
    return get_hebbian_stats(engine)


@app.patch("/api/assets/{crystal_id}")
def patch_asset(crystal_id: str, payload: AssetPatchRequest):
    try:
        update_asset(engine, crystal_id, payload.layer or "", payload.fixed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}

@app.delete("/api/assets/{crystal_id}")
def delete_asset(crystal_id: str):
    if not remove_asset(files, engine, crystal_id):
        raise HTTPException(status_code=404, detail="晶体不存在")
    return {"ok": True}

@app.get("/api/pending")
def pending():
    return {"cards": pending_cards(files)}

@app.post("/api/pending/{card_id}/confirm")
def confirm_pending(card_id: str, payload: PendingConfirmRequest):
    try:
        result = confirm_pending_card(
            files,
            engine,
            card_id,
            payload.content,
            payload.force,
        )
    except ValueError as e:
        if str(e) == "卡片不存在":
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/pending/{card_id}/ignore")
def ignore_pending(card_id: str):
    ignore_pending_card(files, card_id)
    return {"ok": True}

@app.get("/api/tasks")
def tasks():
    return {"tasks": task_cards(files)}

@app.post("/api/tasks/{task_id}/resolve")
def resolve_task(task_id: str):
    try:
        mark_task_done(files, engine, task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}

@app.post("/api/tasks/{task_id}/ignore")
def ignore_task(task_id: str):
    try:
        mark_task_ignored(files, task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}

@app.get("/api/status")
def status():
    return system_status(files)

@app.get("/api/holes")
def holes():
    return holes_snapshot(files, engine)

@app.get("/api/today")
def today():
    return today_snapshot(files)

@app.get("/api/health")
def health():
    return system_health(Config, HealthChecker)
@app.get("/api/health-dashboard")
async def health_dashboard(user: auth.User = Depends(auth.get_current_user)):
    """返回系统健康度 + 用户订阅信息"""
    return build_health_dashboard(engine, auth, user)

@app.post("/api/search")
def search(payload: SearchRequest):
    return search_documents(
        SearchService,
        payload.keyword,
        payload.dirs,
        payload.regex,
    )

@app.post("/api/daily-plan/run")
def daily_plan(payload: DailyPlanRequest, background: BackgroundTasks, user: User = Depends(get_current_user)):
    effective_key = _user_effective_key(user, payload.api_key)
    job_id = job_manager.create("daily-plan")
    stop_event = threading.Event()
    job_manager.stop_flags[job_id] = stop_event

    def task():
        def progress(data: Dict[str, Any]):
            job_manager.set(job_id, progress=data.get("progress", 0), daily_progress=data)

        try:
            return run_daily_plan_task(
                engine,
                AIClient,
                ExternalFetcher,
                lambda engine, ai, fetcher, log, status: DailyPlanner(
                    engine,
                    ai,
                    fetcher,
                    log,
                    status,
                ),
                effective_key,
                payload.intent_keywords,
                payload.time_budget_seconds,
                stop_event.is_set,
                progress,
                lambda m, level="system": job_manager.log(job_id, m, level),
                lambda m: job_manager.log(job_id, m, "status"),
            )
        finally:
            job_manager.stop_flags.pop(job_id, None)

    background.add_task(job_manager.run, job_id, task)
    return {"job_id": job_id}

@app.post("/api/daily-plan/stop/{job_id}")
def stop_daily_plan(job_id: str):
    if job_id in job_manager.stop_flags:
        job_manager.stop_flags[job_id].set()
        job_manager.log(job_id, "收到中断请求，正在整理已产生成果...", "warning")
        job_manager.set(job_id, status="stopping")
        return {"ok": True}
    raise HTTPException(status_code=404, detail="每日计划任务不存在或已结束")


def main() -> None:
    """Web 服务入口：uvicorn 启动。"""
    import uvicorn

    uvicorn.run("access.web:app", host="0.0.0.0", port=8000)



