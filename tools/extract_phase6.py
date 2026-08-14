#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract alarm monitor and force explorer from the 2.2 monolith.

Usage:
    python tools/extract_phase6.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


ALARM_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from governance.config import Config

"""

FORCE_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List

from external.fetcher import ExternalFetcher
from governance.config import Config

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase6.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    alarm_content = ALARM_HEADER + slice_lines(4626, 4748)

    force_content = FORCE_HEADER + slice_lines(5724, 5997)
    force_content = force_content.replace("engine: 'CrystalEngine'", "engine: Any")
    force_content = force_content.replace(
        "from crystal_tree_all_in_one_day import AIClient",
        "from external.ai_client import AIClient",
    )

    targets = {
        root / "harness" / "alarm.py": alarm_content,
        root / "harness" / "force_explorer.py": force_content,
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
