#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Web API from the 2.2 monolith into access/web.py.

Usage:
    python tools/extract_phase16.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


WEB_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth
from auth import User, consume_monthly_quota, get_current_user, get_remaining_quota
from data.storage import DBManager, FileIO
from external.ai_client import AIClient
from external.fetcher import ExternalFetcher
from external.network import NetworkManager
from external.search import SearchService
from governance.config import Config
from harness.engine import CrystalEngine
from harness.processors.batch_processor import BatchProcessor
from harness.processors.debate import DebateEngine
from evolution.meta_search import MetaSearchEngine
from harness.processors.planner import DailyPlanner
from harness.reporting import build_debate_report_markdown, polish_report_markdown
from harness.twin_workbench import TwinWorkbench

PROJECT_ROOT = Path(__file__).resolve().parent.parent

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase16.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    content = WEB_HEADER + "".join(lines[21080:22468])
    target = root / "access" / "web.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
