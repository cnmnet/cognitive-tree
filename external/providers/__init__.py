#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部搜索 Provider 集合。"""

from external.providers.arxiv_provider import ArxivProvider
from external.providers.baidu_qianfan import BaiduQianfanProvider
from external.providers.base import BaseSearchProvider, SearchResult
from external.providers.semantic_scholar import SemanticScholarProvider

__all__ = [
    "ArxivProvider",
    "BaiduQianfanProvider",
    "BaseSearchProvider",
    "SearchResult",
    "SemanticScholarProvider",
]
