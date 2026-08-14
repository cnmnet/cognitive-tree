#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract report builders from the 2.2 monolith into harness/reporting.py.

Usage:
    python tools/extract_phase3.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


REPORTING_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase3.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    content = (
        REPORTING_HEADER
        + slice_lines(14296, 14339)
        + "\n"
        + slice_lines(14342, 14578)
        + "\n"
        + slice_lines(14581, 14622)
        + "\n"
    )
    target = root / "harness" / "reporting.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
