"""Web ????????????????????"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional


class LegacyProcessManager:
    """管理原 GUI 子进程的启动/停止，避免 Web 路由直接持有进程状态。"""

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def login(
        self,
        username: str,
        password: str,
        project_root: Any,
        config: Any,
    ) -> Dict[str, Any]:
        if not username.strip() or password != "111111":
            raise ValueError("用户名或密码错误")
        if self.is_running():
            return {"ok": True, "running": True, "message": "原后端界面已在运行"}

        cmd = [sys.executable, "-m", "access.gui"]
        env = os.environ.copy()
        env.setdefault("CRYSTAL_TREE_DATA_ROOT", str(config.DATA_ROOT))
        env["PYTHONIOENCODING"] = "utf-8"

        log_dir = config.DATA_ROOT / "系统日志"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "gui_subprocess.log"

        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"=== 启动时间: {datetime.now().isoformat()} ===\n")
            f.write(f"命令: {' '.join(cmd)}\n")
            f.write(f"工作目录: {str(project_root)}\n")
            f.write(f"数据目录: {env.get('CRYSTAL_TREE_DATA_ROOT')}\n")
            f.write("=" * 60 + "\n")
            f.flush()

            try:
                self.process = subprocess.Popen(
                    cmd,
                    cwd=str(project_root),
                    env=env,
                    stdout=f,
                    stderr=f,
                    creationflags=(
                        subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
                    ),
                    text=True,
                )
            except Exception as e:
                f.write(f"启动异常: {e}\n")
                raise RuntimeError(f"启动失败: {e}")

        time.sleep(1.0)
        if self.process.poll() is not None:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    error_output = f.read()
            except OSError:
                error_output = "无法读取日志文件"
            raise RuntimeError(
                f"老师端启动后立即退出。请查看日志：{log_file}\n\n"
                f"日志内容：\n{error_output[-1000:]}"
            )

        return {
            "ok": True,
            "running": True,
            "message": f"已启动老师端界面（独立窗口），日志见 {log_file}",
        }

    def logout(self) -> Dict[str, Any]:
        if self.process is None or self.process.poll() is not None:
            self.process = None
            return {
                "ok": True,
                "running": False,
                "message": "原后端界面未运行，前端可继续使用",
            }
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process = None
        return {"ok": True, "running": False, "message": "已退出原后端登录，前端可继续使用"}
