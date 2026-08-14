#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract vector store, fingerprint extractor and layer audit service.

Usage:
    python tools/extract_phase5.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


VECTOR_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, List, Tuple

from governance.config import Config

"""

FINGERPRINT_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from core.models import CognitiveFingerprint

"""

AUDIT_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from governance.config import Config

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase5.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    vector_content = VECTOR_HEADER + slice_lines(4753, 4943)
    vector_content = vector_content.replace("file_io: FileIO", "file_io: Any")

    fingerprint_content = FINGERPRINT_HEADER + slice_lines(4952, 5481)
    fingerprint_content = fingerprint_content.replace(
        "engine: 'CrystalEngine', file_io: FileIO",
        "engine: Any, file_io: Any",
    )

    audit_content = AUDIT_HEADER + slice_lines(6449, 6897)
    audit_content = audit_content.replace(
        "engine: 'CrystalEngine', file_io: FileIO",
        "engine: Any, file_io: Any",
    )

    targets = {
        root / "data" / "vector_store.py": vector_content,
        root / "core" / "fingerprint.py": fingerprint_content,
        root / "harness" / "audit.py": audit_content,
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
