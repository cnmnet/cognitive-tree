#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract planners and twin workbench from the 2.2 monolith.

Usage:
    python tools/extract_phase14.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


PLANNER_HEADER = """#!/usr/bin/env python3
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

from core.models import Crystal, Hole, TaskCard
from data.storage import FileIO
from external.ai_client import AIClient
from external.fetcher import ExternalFetcher
from external.search import SearchService
from governance.config import Config
from harness.contemplative import ContemplativeEngine
from harness.engine import CrystalEngine
from harness.processors.batch_processor import BatchProcessor
from harness.processors.debate import DebateEngine

"""

TWIN_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from external.ai_client import AIClient
from governance.config import Config
from harness.contemplative import ContemplativeEngine
from harness.engine import CrystalEngine
from harness.processors.debate import DebateEngine

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase14.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    planner_content = (
        PLANNER_HEADER
        + slice_lines(13156, 13330)
        + slice_lines(13334, 13523)
        + slice_lines(13528, 14288)
    )
    twin_content = TWIN_HEADER + slice_lines(25114, 25617)

    targets = {
        root / "harness" / "processors" / "planner.py": planner_content,
        root / "harness" / "twin_workbench.py": twin_content,
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
