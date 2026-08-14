#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract config, models, storage and dependency sections from the 2.2 monolith.

Usage:
    python tools/extract_phase1.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


CONFIG_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

"""

MODELS_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional

"""

STORAGE_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .config import Config
from .models import HealthCheckResult

"""

DEPENDENCIES_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

MODELS_TAIL = """
@dataclass
class Report:
    title: str
    sections: Dict[str, Any] = field(default_factory=dict)
    source_question: str = ""
    created_at: str = ""
"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase1.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    targets = {
        root / "governance" / "config.py": (
            CONFIG_HEADER + slice_lines(85, 496)
        ),
        root / "core" / "benchmarks.py": (
            "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\n"
            + slice_lines(501, 512)
            + "\n"
        ),
        root / "core" / "models.py": (
            MODELS_HEADER + slice_lines(520, 577) + slice_lines(879, 971) + MODELS_TAIL
        ),
        root / "core" / "dependencies.py": (
            DEPENDENCIES_HEADER
            + slice_lines(582, 646)
            + "\n\n__all__ = [\n"
            + '    "REQUESTS_AVAILABLE", "requests", "HTTPAdapter", "Retry",\n'
            + '    "BS4_AVAILABLE", "BeautifulSoup",\n'
            + '    "pd", "Document", "HAS_DOCX", "PdfReader", "HAS_PDF",\n'
            + '    "Presentation", "HAS_PPTX", "arxiv", "ARXIV_AVAILABLE",\n'
            + '    "SENTENCE_TRANSFORMERS_AVAILABLE",\n'
            + "]\n"
        ),
        root / "data" / "storage.py": (
            STORAGE_HEADER + slice_lines(655, 873) + slice_lines(973, 1074)
        ),
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
