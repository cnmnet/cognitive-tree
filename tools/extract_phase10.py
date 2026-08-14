#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract CrystalEngine from the 2.2 monolith into harness/engine.py.

Usage:
    python tools/extract_phase10.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


ENGINE_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models import CognitiveFingerprint, Conflict, Crystal, Hole, TaskCard
from data.storage import FileIO
from data.vector_store import VectorStore
from evolution.meta_layer import MetaLayer
from governance.config import Config
from harness.alarm import AlarmMonitor
from harness.audit import LayerAuditService
from harness.gate import CheapGate
from harness.rumad import RUMADController

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase10.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    content = ENGINE_HEADER + "".join(lines[6898:9461])
    target = root / "harness" / "engine.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
