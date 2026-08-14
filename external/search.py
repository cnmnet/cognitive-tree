#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from collections import Counter
from typing import List, Tuple

from governance.config import Config

class SearchService:
    @staticmethod
    def _tokens(text: str) -> List[str]:
        tokens = []
        for word in re.findall(r'[A-Za-z0-9_]+|[\u4e00-\u9fff]+', text.lower()):
            if re.search(r'[\u4e00-\u9fff]', word):
                chars = [ch for ch in word if re.match(r'[\u4e00-\u9fff]', ch)]
                tokens.extend(chars)
                tokens.extend(''.join(chars[i:i+2]) for i in range(len(chars)-1))
                tokens.extend(''.join(chars[i:i+3]) for i in range(len(chars)-2))
            else:
                tokens.append(word)
        return [t for t in tokens if t]

    @staticmethod
    def _score(keyword: str, line: str) -> float:
        if not keyword or not line:
            return 0.0
        score = 8.0 if keyword in line else 0.0
        query_terms = Counter(SearchService._tokens(keyword))
        line_terms = Counter(SearchService._tokens(line))
        for term, weight in query_terms.items():
            if term in line_terms:
                score += min(3, line_terms[term]) * min(2, weight)
        return score

    @staticmethod
    def search_documents(keyword: str, dirs: List[str], regex: bool = False) -> List[Tuple[str, int, str]]:
        results = []
        search_dirs = [Config.DATA_ROOT / d for d in dirs]
        pattern = re.compile(keyword) if regex else None
        for sdir in search_dirs:
            if not sdir.exists():
                continue
            for file_path in sdir.rglob("*"):
                if file_path.is_file() and file_path.suffix not in ('.pyc','.db'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line_num, line in enumerate(f, 1):
                                if regex:
                                    if pattern.search(line):
                                        results.append((1000.0, str(file_path.relative_to(Config.DATA_ROOT)), line_num, line.rstrip()))
                                else:
                                    score = SearchService._score(keyword, line)
                                    if score > 0:
                                        results.append((score, str(file_path.relative_to(Config.DATA_ROOT)), line_num, line.rstrip()))
                    except:
                        continue
        results.sort(key=lambda item: item[0], reverse=True)
        return [(file_path, line_num, line) for _, file_path, line_num, line in results]

