#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the meta layer from the 2.2 monolith into evolution/meta_layer.py.

Usage:
    python tools/extract_phase9.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


META_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from core.models import TaskCard
from evolution.godel import GödelAgent
from governance.config import Config
from governance.prompt_templates import PromptTemplate, PromptTemplateManager
from harness.assurance.anti_fraud import AIPersonaDetector, CrossLingualAuditor, StarlinkFingerprintDB
from harness.force_explorer import ForceExplorer

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase9.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    content = META_HEADER + "".join(lines[2870:4621])
    content = content.replace(
        "engine: 'CrystalEngine', file_io: FileIO, ai_client=None",
        "engine: Any, file_io: Any, ai_client=None",
    )

    target = root / "evolution" / "meta_layer.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
