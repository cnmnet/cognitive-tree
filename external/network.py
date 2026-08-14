#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import random
import time
from typing import Callable

import requests

from core.dependencies import HTTPAdapter, REQUESTS_AVAILABLE, Retry
from governance.config import Config

class NetworkManager:
    _shared_session = None

    @classmethod
    def _get_session(cls):
        if not REQUESTS_AVAILABLE:
            return None
        if cls._shared_session is None:
            session = requests.Session()
            retry_strategy = Retry(total=Config.MAX_RETRIES, backoff_factor=Config.BACKOFF_FACTOR, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","HEAD"])
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            cls._shared_session = session
        return cls._shared_session

    @classmethod
    def get_random_user_agent(cls) -> str:
        return random.choice(Config.USER_AGENTS)

    @classmethod
    def safe_request(cls, url: str, use_mirror: bool = False, log_callback: Callable = None, **kwargs):
        if not REQUESTS_AVAILABLE:
            return None
        session = cls._get_session()
        if session is None:
            return None
        time.sleep(random.uniform(*Config.DELAY_BETWEEN_REQUESTS))
        final_url = url
        if use_mirror and "huggingface.co" in url:
            final_url = url.replace("https://huggingface.co", Config.HF_MIRROR)
        headers = kwargs.get('headers', {})
        headers.update({'User-Agent': cls.get_random_user_agent(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', 'Connection': 'keep-alive'})
        kwargs['headers'] = headers
        kwargs['timeout'] = Config.TIMEOUT
        try:
            response = session.get(final_url, **kwargs)
            response.raise_for_status()
            if response.status_code == 200 and len(response.content) > 100:
                return response
            return None
        except Exception as e:
            if log_callback:
                log_callback(f"请求失败 {type(e).__name__}: {final_url}", "warning")
            return None

