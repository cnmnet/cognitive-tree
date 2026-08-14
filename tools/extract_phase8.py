#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the Goedel agent from the 2.2 monolith into evolution/godel.py.

Usage:
    python tools/extract_phase8.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


GODEL_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.benchmarks import BENCHMARK_QUESTIONS
from external.fetcher import ExternalFetcher
from governance.config import Config
from governance.prompt_templates import PromptTemplateManager

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase8.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    content = GODEL_HEADER + "".join(lines[1284:2529])
    content = content.replace(
        "engine: 'CrystalEngine', ai_client: 'AIClient',\n                 template_manager: PromptTemplateManager",
        "engine: Any, ai_client: Any,\n                 template_manager: PromptTemplateManager",
    )

    target = root / "evolution" / "godel.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
