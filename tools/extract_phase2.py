#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract network, AI client, external fetcher and search from the 2.2 monolith.

Usage:
    python tools/extract_phase2.py <monolith.py> <dest_root>
"""

from __future__ import annotations

import sys
from pathlib import Path


NETWORK_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import random
import time
from typing import Callable

import requests

from core.dependencies import HTTPAdapter, REQUESTS_AVAILABLE, Retry
from governance.config import Config

"""

AI_CLIENT_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import requests

from core.dependencies import REQUESTS_AVAILABLE
from governance.config import Config

"""

FETCHER_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from typing import Callable, Dict, List
from urllib.parse import quote

import requests

from core.dependencies import ARXIV_AVAILABLE, BS4_AVAILABLE, BeautifulSoup, HTTPAdapter, REQUESTS_AVAILABLE, Retry
from data.storage import FileIO
from external.network import NetworkManager
from governance.config import Config

"""

SEARCH_HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import List, Tuple

from governance.config import Config

"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_phase2.py <monolith.py> <dest_root>", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    root = Path(sys.argv[2])
    lines = monolith.read_text(encoding="utf-8").splitlines(keepends=True)

    def slice_lines(start: int, end: int) -> str:
        return "".join(lines[start - 1 : end])

    targets = {
        root / "external" / "network.py": NETWORK_HEADER + slice_lines(1082, 1127),
        root / "external" / "ai_client.py": (
            AI_CLIENT_HEADER + slice_lines(9466, 9653) + "\n\n" + slice_lines(9658, 9678)
        ),
        root / "external" / "fetcher.py": FETCHER_HEADER + slice_lines(9685, 10173),
        root / "external" / "search.py": SEARCH_HEADER + slice_lines(10179, 10229),
    }

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path} ({len(content.splitlines())} lines)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
