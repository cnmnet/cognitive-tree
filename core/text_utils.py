"""跨层共享的纯文本工具。"""

from __future__ import annotations

import re
from typing import Any


def normalize_text(content: Any, limit: int = 80) -> str:
    """压缩连续空白并截断，供晶体/孔洞内容统一使用。"""
    return re.sub(r"\s+", " ", str(content or "")).strip()[:limit]


def count_output_words(text: Any) -> int:
    """统计输出字数：中日韩字符逐个计 1，英文/数字按连续词计 1，忽略空白与标点。"""
    content = str(text or "")
    word_re = re.compile(
        r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]"
        r"|[A-Za-z0-9]+(?:[._\-/][A-Za-z0-9]+)*"
    )
    return len(word_re.findall(content))
