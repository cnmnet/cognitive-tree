
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双击启动认知晶体树 Web 并自动打开浏览器。"""

from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def _pause() -> None:
    try:
        input("按回车退出...")
    except EOFError:
        pass


def main() -> int:
    port = int(os.getenv("CRYSTAL_TREE_PORT", "8788"))
    url = f"http://127.0.0.1:{port}"

    if not os.getenv("DEEPSEEK_API_KEY"):
        print("警告：未设置 DEEPSEEK_API_KEY，Web 可以启动，但 AI 功能需要 API Key。")

    if _port_in_use(port):
        print(f"检测到 {url} 已有服务在运行，直接打开浏览器。")
        webbrowser.open(url)
        _pause()
        return 0

    from access.web import app
    import uvicorn

    print(f"正在启动认知晶体树 Web：{url}")
    print("浏览器将自动打开，按 Ctrl+C 停止服务。")
    try:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        uvicorn.run(app, host="127.0.0.1", port=port)
        return 0
    except OSError as exc:
        print(f"启动失败：{exc}")
        _pause()
        return 1


if __name__ == "__main__":
    sys.exit(main())
