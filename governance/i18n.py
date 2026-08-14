"""Minimal i18n helper for CLI/Web messages."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"


@lru_cache(maxsize=2)
def _catalog(lang: str) -> Dict[str, str]:
    try:
        return dict(
            json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        )
    except Exception:
        return {}


def tr(key: str, lang: str = "zh_CN", **kwargs: Any) -> str:
    """按语言返回文案；缺失时回退中文，再回退 key。"""
    lang = {"zh_CN": "zh_CN", "en_US": "en_US"}.get(lang, "zh_CN")
    text = _catalog(lang).get(key) or _catalog("zh_CN").get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
