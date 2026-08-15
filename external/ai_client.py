#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import requests

from core.dependencies import REQUESTS_AVAILABLE
from governance.config import Config


def aggregate_call_log(logs: List[Dict] = None) -> Dict[str, int]:
    """汇总 AIClient.CALL_LOG 的真实 token 用量（含缓存命中/未命中）。"""
    entries = AIClient.CALL_LOG if logs is None else logs
    totals = {
        "calls": len(entries),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
        "by_caller": {},
    }
    for entry in entries:
        prompt = int(entry.get("prompt_tokens", 0) or 0)
        completion = int(entry.get("completion_tokens", 0) or 0)
        cache_hit = int(entry.get("prompt_cache_hit_tokens", 0) or 0)
        cache_miss = int(entry.get("prompt_cache_miss_tokens", 0) or 0)
        totals["prompt_tokens"] += prompt
        totals["completion_tokens"] += completion
        totals["total_tokens"] += prompt + completion
        totals["prompt_cache_hit_tokens"] += cache_hit
        totals["prompt_cache_miss_tokens"] += cache_miss
        caller = str(entry.get("caller") or "unknown")
        item = totals["by_caller"].setdefault(
            caller,
            {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 0,
            },
        )
        item["calls"] += 1
        item["prompt_tokens"] += prompt
        item["completion_tokens"] += completion
        item["total_tokens"] += prompt + completion
        item["prompt_cache_hit_tokens"] += cache_hit
        item["prompt_cache_miss_tokens"] += cache_miss
    return totals


class AIClient:
    CALL_LOG: list = []

    def __init__(self, api_key: str = None, api_url: str = None):
        self.api_key = api_key or Config.get_api_key()
        self.api_url = api_url or Config.DEEPSEEK_API_URL
        self._session = None
        self._has_requests = REQUESTS_AVAILABLE
        # 埋点统计属性（Day 0 新增）
        self._call_count = 0
        self._token_estimate = 0
        self._total_time = 0.0

    @property
    def session(self):
        if not self._has_requests:
            return None
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _call_api(self, messages: List[Dict], temperature: float = 0.7,
                  response_format: Dict = None, stream: bool = False,
                  callback: Callable[[str], None] = None,
                  max_tokens: int = None, caller: str = None) -> Optional[str]:
        # === 1. 初始化 result 为 None（防御性编程） ===
        result = None
        start_time = time.time()
        total_chars = sum(len(m.get("content", "")) for m in messages)
        token_used = total_chars // 2
        self._token_estimate += token_used
        self._call_count += 1

        # === 2. 校验 API Key ===
        if not self.api_key:
            result = "错误：未配置 DEEPSEEK_API_KEY"
        elif not self._has_requests:
            result = "错误：需要安装 requests 库"
        else:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": temperature,
                "stream": stream,
            }
            if max_tokens is not None:
                payload["max_tokens"] = min(8000, max(100, int(max_tokens)))
            else:
                payload["max_tokens"] = 4000
            if response_format:
                payload["response_format"] = response_format

            # === 3. 请求执行（完整异常捕获） ===
            try:
                if stream:
                    with self.session.post(self.api_url, headers=headers, json=payload,
                                           stream=True, timeout=120) as resp:
                        resp.raise_for_status()
                        collected = ""
                        for line in resp.iter_lines():
                            if line:
                                line = line.decode('utf-8')
                                if line.startswith('data: '):
                                    data = line[6:]
                                    if data == '[DONE]':
                                        break
                                    try:
                                        chunk = json.loads(data)
                                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                                        content = delta.get('content', '')
                                        if content:
                                            collected += content
                                            if callback:
                                                callback(content)
                                    except json.JSONDecodeError:
                                        continue
                        result = collected if collected else "（AI返回空内容）"
                else:
                    resp = self.session.post(self.api_url, headers=headers, json=payload, timeout=60)
                    resp.raise_for_status()
                    try:
                        response_data = resp.json()
                        usage = response_data.get("usage") or {}
                        call_caller = caller or sys._getframe(1).f_code.co_name
                        AIClient.CALL_LOG.append(
                            {
                                "caller": call_caller,
                                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                                "completion_tokens": int(usage.get("completion_tokens", 0)),
                                "prompt_cache_hit_tokens": int(usage.get("prompt_cache_hit_tokens", 0) or 0),
                                "prompt_cache_miss_tokens": int(usage.get("prompt_cache_miss_tokens", 0) or 0),
                            }
                        )
                        if len(AIClient.CALL_LOG) > 2000:
                            del AIClient.CALL_LOG[: len(AIClient.CALL_LOG) - 2000]
                        result = response_data["choices"][0]["message"]["content"]
                        if not result:
                            result = "（AI返回空内容）"
                    except (KeyError, json.JSONDecodeError, IndexError) as e:
                        result = f"AI响应解析失败: {e}"
            except requests.exceptions.Timeout:
                result = "错误：请求超时（请检查网络或增大超时设置）"
            except requests.exceptions.ConnectionError:
                result = "错误：网络连接失败（请检查网络或API地址）"
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    result = "错误：API Key 无效或已过期"
                elif e.response.status_code == 429:
                    result = "错误：请求频率过高，请稍后重试"
                else:
                    result = f"错误：HTTP {e.response.status_code} - {e.response.text[:100]}"
            except Exception as e:
                result = f"AI调用失败: {type(e).__name__} - {str(e)}"

        # === 4. 最终保护：如果 result 仍为 None ===
        if result is None:
            result = "错误：未知原因导致返回为空"

        # === 5. 埋点 ===
        elapsed = time.time() - start_time
        self._total_time += elapsed
        if self._call_count % 10 == 0:
            self._write_metrics()

        return result
    
    def _write_metrics(self):
        """将埋点统计数据写入 系统日志/埋点数据.json"""
        log_path = Config.DATA_ROOT / "系统日志" / "埋点数据.json"
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"TTQ": [], "TTA": [], "TTU": []}

        # 记录当前累计值（每次记录是一个快照）
        data["TTQ"].append({
            "timestamp": datetime.now().isoformat(),
            "call_count": self._call_count,
            "total_tokens": self._token_estimate,
            "avg_tokens_per_call": round(self._token_estimate / self._call_count, 2) if self._call_count else 0
        })
        data["TTA"].append({
            "timestamp": datetime.now().isoformat(),
            "call_count": self._call_count,
            "total_time_seconds": round(self._total_time, 3),
            "avg_time_per_call": round(self._total_time / self._call_count, 3) if self._call_count else 0
        })
        data["TTU"].append({
            "timestamp": datetime.now().isoformat(),
            "call_count": self._call_count,
            "total_tokens_used": self._token_estimate,
        })

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def chat(self, prompt: str, system: str = "你是认知晶体树的AI协作者，请友好自然地回答问题。",
             temperature: float = 0.7, max_tokens: int = None) -> str:
        return self._call_api(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
    def chat_with_history(self, history: List[Tuple[str, str]], system: str = "你是认知晶体树的AI协作者，请友好自然地回答问题。", context: str = "") -> str:
        if context:
            system = system + context
        messages = [{"role": "system", "content": system}]
        for role, content in history:
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
        return self._call_api(messages)

    def chat_json(self, prompt: str, temperature: float = 0.3) -> Dict:
        result = self._call_api([{"role": "user", "content": prompt}], temperature=temperature, response_format={"type": "json_object"})
        if not isinstance(result, str):
            return {"error": "AI返回为空"}
        if result.startswith("错误") or result.startswith("AI调用失败"):
            return {"error": result}
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        if not cleaned.startswith("{"):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                cleaned = cleaned[start:end+1]
        try:
            return json.loads(cleaned)
        except:
            return {"error": "解析JSON失败", "raw": result}

    def chat_stream(self, prompt: str, system: str = "你是认知晶体树的AI协作者，请友好自然地回答问题。",
                    callback: Callable[[str], None] = None, max_tokens: int = None) -> str:
        """
        流式对话，支持逐块回调。
        """
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        return self._call_api(messages, stream=True, callback=callback, max_tokens=max_tokens)



def generate_session_title_from_content(content: str, api_key: str = None) -> str:
    """
    调用 AI 为会话生成精炼标题（不超过 8 个字）
    如果 AI 调用失败，则降级为本地提取可读标题。
    """
    if not content:
        return ""
    ai = AIClient(api_key=api_key or Config.get_api_key())
    try:
        result = ai.chat_json(
            f"请为以下对话生成一个不超过 8 个字的精炼标题，只返回 JSON：{{'title': '你的标题'}}\n\n内容：{content[:300]}",
            temperature=0.1
        )
        if "error" not in result:
            title = result.get("title", "").strip()
            if title:
                return title
    except Exception:
        pass
    return fallback_session_title(content)


def fallback_session_title(content: str) -> str:
    """AI 标题不可用时，从首条消息中提取可读的短标题。"""
    text = re.sub(r"\s+", " ", content or "").strip()
    # 去掉 [深度推理-多角色] / 【晶体化】 这类功能前缀
    text = re.sub(r"^[\[【][^\]】]+[\]】]\s*", "", text)
    text = re.sub(r"^(请|帮我|你好|我想|我们要|请问)\s*", "", text)
    # 优先截取带引号的具体问题
    quoted = re.search(r"[“\"']([^”\"']{4,20})[”\"']", text)
    if quoted:
        return quoted.group(1).strip()[:10]
    # 去掉常见开头词后取前 10 个字符
    for marker in ("？", "?", "。", ".", "，", ",", "，", " ", "；", ";"):
        idx = text.find(marker)
        if 4 <= idx <= 16:
            return text[:idx].strip()[:10]
    return text[:10].strip()
