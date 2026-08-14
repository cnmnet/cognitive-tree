#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract CrystalTreeApp GUI from the 2.2 monolith into access/gui.py.

Usage:
    python tools/extract_phase15.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


GUI_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import Toplevel, filedialog, messagebox, scrolledtext, simpledialog, ttk
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.models import CognitiveFingerprint, Conflict, Crystal, Hole, TaskCard
from data.storage import FileIO
from external.ai_client import AIClient
from external.fetcher import ExternalFetcher
from governance.config import Config
from governance.prompt_templates import PromptTemplateManager
from harness.engine import CrystalEngine
from harness.orchestrator import OutputOrchestrator
from harness.processors.batch_processor import BatchProcessor
from harness.processors.debate import DebateContext, DebateEngine, DebateRole
from harness.processors.planner import DailyPlanner
from harness.reporting import (
    _dedupe_headings,
    _extract_step_blocks,
    _join_broken_lines,
    build_debate_report_markdown,
    polish_report_markdown,
)

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase15.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    content = GUI_HEADER + "".join(lines[14624:21068])
    target = root / "access" / "gui.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
