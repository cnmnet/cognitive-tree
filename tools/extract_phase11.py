#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract DebateEngine from the 2.2 monolith into harness/processors/debate.py.

Usage:
    python tools/extract_phase11.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


DEBATE_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import random
import re
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.models import Crystal, Hole
from external.ai_client import AIClient
from external.fetcher import ExternalFetcher
from external.search import SearchService
from governance.config import Config
from harness.alarm import AlarmMonitor
from harness.engine import CrystalEngine
from harness.reporting import build_debate_report_markdown, polish_report_markdown
from harness.rumad import RUMADController

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase11.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    content = DEBATE_HEADER + "".join(lines[10337:13155])
    target = root / "harness" / "processors" / "debate.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
