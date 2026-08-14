#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract prompt templates and anti-fraud modules from the 2.2 monolith.

Usage:
    python tools/extract_phase7.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


TEMPLATE_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from governance.config import Config

"""

ANTI_FRAUD_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase7.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    template_content = TEMPLATE_HEADER + slice_lines(1135, 1283)
    template_content = template_content.replace("file_io: FileIO", "file_io: Any")

    anti_fraud_content = ANTI_FRAUD_HEADER + slice_lines(2534, 2862)
    anti_fraud_content = anti_fraud_content.replace("ai_client: 'AIClient' = None", "ai_client: Any = None")

    targets = {
        root / "governance" / "prompt_templates.py": template_content,
        root / "harness" / "assurance" / "anti_fraud.py": anti_fraud_content,
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
