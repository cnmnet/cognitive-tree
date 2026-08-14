#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Day12 modules, batch processor and contemplative engine.

Usage:
    python tools/extract_phase13.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


CLAIM_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from harness.engine import CrystalEngine

"""

SVR_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from governance.config import Config
from harness.engine import CrystalEngine

"""

SANDBOX_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from data.storage import FileIO
from governance.config import Config

"""

M3MAD_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Dict

from external.ai_client import AIClient
from harness.engine import CrystalEngine

"""

DAY12_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List

from external.ai_client import AIClient
from harness.engine import CrystalEngine
from harness.assurance.claim_extractor import ClaimExtractor, VerifiableClaim
from harness.assurance.m3mad import M3MADBench, M3MADBenchResult
from harness.assurance.sandbox import SandboxExecutor
from harness.assurance.svr_mad import SVRMADValidator

"""

BATCH_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Callable, List

from core.dependencies import Document, HAS_DOCX, HAS_PDF, HAS_PPTX, PdfReader, Presentation, pd
from external.ai_client import AIClient

"""

CONTEMPLATIVE_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from external.ai_client import AIClient
from harness.engine import CrystalEngine

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase13.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    targets = {
        root / "harness" / "assurance" / "claim_extractor.py": CLAIM_HEADER + slice_lines(23717, 24051),
        root / "harness" / "assurance" / "svr_mad.py": SVR_HEADER + slice_lines(24052, 24185),
        root / "harness" / "assurance" / "sandbox.py": SANDBOX_HEADER + slice_lines(24186, 24454),
        root / "harness" / "assurance" / "m3mad.py": M3MAD_HEADER + slice_lines(24460, 24726),
        root / "harness" / "assurance" / "day12_integration.py": DAY12_HEADER + slice_lines(24727, 24898),
        root / "harness" / "processors" / "batch_processor.py": BATCH_HEADER + slice_lines(10235, 10329),
        root / "harness" / "contemplative.py": CONTEMPLATIVE_HEADER + slice_lines(25128, 25372),
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
