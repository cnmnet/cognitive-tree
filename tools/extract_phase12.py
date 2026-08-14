#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract output orchestrator from the 2.2 monolith into harness/orchestrator.py.

Usage:
    python tools/extract_phase12.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


ORCH_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from external.ai_client import AIClient
from governance.config import Config
from harness.engine import CrystalEngine

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase12.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    content = ORCH_HEADER + "".join(lines[22708:23619])
    content = content.replace("'AIClient'", "AIClient")
    content = content.replace("'CrystalEngine'", "CrystalEngine")

    target = root / "harness" / "orchestrator.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
