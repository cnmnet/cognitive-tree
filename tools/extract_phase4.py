#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract RUMAD controller and cheap gate from the 2.2 monolith.

Usage:
    python tools/extract_phase4.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


RUMAD_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

"""

GATE_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from governance.config import Config

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase4.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    targets = {
        root / "harness" / "rumad.py": RUMAD_HEADER + slice_lines(6006, 6440),
        root / "harness" / "gate.py": GATE_HEADER + slice_lines(5487, 5719),
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
