#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后台任务与会话状态管理：Web/未来接入层共用，不持有 UI 状态。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any, Dict


class JobManager:
    """临时任务状态容器：接入层后台任务只通过它读写状态。"""

    def __init__(self) -> None:
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.stop_flags: Dict[str, threading.Event] = {}
        self.lock = threading.Lock()

    def create(self, job_type: str) -> str:
        with self.lock:
            job_id = f"{job_type}-{uuid.uuid4().hex[:10]}"
            self.jobs[job_id] = {
                "id": job_id,
                "type": job_type,
                "status": "queued",
                "progress": 0,
                "logs": [],
                "result": None,
                "error": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            return job_id

    def set(self, job_id: str, **kwargs: Any) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.update(kwargs)
            job["updated_at"] = datetime.now().isoformat()

    def log(self, job_id: str, message: str, level: str = "system") -> None:
        with self.lock:
            self.jobs[job_id]["logs"].append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "level": level,
                    "message": message,
                }
            )
            self.jobs[job_id]["updated_at"] = datetime.now().isoformat()

    def run(self, job_id: str, fn: Any) -> None:
        self.set(job_id, status="running", progress=5)
        try:
            result = fn()
            self.set(job_id, status="done", progress=100, result=result)
        except Exception as exc:
            self.set(job_id, status="error", error=str(exc))
            self.log(job_id, f"任务失败：{exc}", "error")
