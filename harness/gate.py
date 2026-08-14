#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from governance.config import Config

class CheapGate:
    """
    便宜门规则引擎

    在调用 LLM 之前先用低成本规则过滤请求。
    只有通过便宜门检查的请求才交给 LLM 处理。

    对应建议2：用"便宜门→LLM"原则降本
    """

    def __init__(self, engine: Any, file_io: Any, log_callback=None):
        self.engine = engine
        self.files = file_io
        self.log = log_callback or (lambda msg, level="system": print(msg))
        self._search_counter = 0
        self._search_threshold = 3

    def _sanitize_user_input(self, text: str) -> tuple:
        """修正极端输入值，返回 (修正后文本, 提示消息)。"""
        if not text:
            return text, ""
        pattern = r'(预算|成本|投入|资金)\s*[：:]?\s*(\d+)\s*(元|万|千|百)?'
        match = re.search(pattern, text)
        if not match:
            return text, ""
        amount = int(match.group(2))
        unit = match.group(3) or "元"
        if unit == "元" and amount < 10000:
            corrected = re.sub(r'(\d+)\s*(元)', r'10万（原输入 \1元，已修正为合理区间）', text)
            return corrected, f"✅ 已将预算从 {amount}元 修正为 10万元（合理区间）"
        return text, ""

    def _estimate_complexity(self, user_input: str) -> str:
        """
        评估问题复杂度：返回 'simple', 'medium', 'high'
        """
        q_len = len(user_input.strip())
        config = Config.ROUTING_CONFIG
        
        # 1. 检查是否包含复杂关键词
        has_complex = any(kw in user_input for kw in config["complex_keywords"])
        
        # 2. 长度极短且无复杂词 → 简单
        if q_len <= config["simple_length_threshold"] and not has_complex:
            return "simple"
        
        # 3. 长度中等且有复杂词 → 中等
        if q_len <= config["medium_length_threshold"] and has_complex:
            return "medium"
        
        # 4. 长度较长且有复杂词 → 高
        if q_len > config["medium_length_threshold"] and has_complex:
            return "high"
        
        # 5. 其他情况（比如长度长但无复杂词）视为中等
        if q_len > config["simple_length_threshold"]:
            return "medium"
        return "simple"

    def check(self, user_input: str, history: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        动态路由决策。

        根据输入复杂度和历史记录，决定后续处理策略。

        Returns:
            包含以下字段的字典：
            - action (str): 执行动作，可选 "rule_engine", "cheap_gate_llm", "direct_llm"
            - complexity (str): 复杂度等级，可选 "simple", "medium", "high"
            - skip_llm (bool): 是否跳过 LLM 调用
            - token_budget (int): 分配的 token 预算
            - cost_estimate (float): 预估成本（美元）
            - reason (str): 决策原因
        """
        # 0. 输入极端值修正
        corrected_input, correction_message = self._sanitize_user_input(user_input)
        if correction_message:
            user_input = corrected_input
            self.log(correction_message, "warning")

        # 1. 评估复杂度
        complexity = self._estimate_complexity(user_input)
        
        # 2. 根据复杂度选择路由
        config = Config.ROUTING_CONFIG
        if complexity == "simple":
            action = "rule_engine"
            skip_llm = True
            token_budget = config["token_budget_simple"]
            reason = "简单问题（短文本/明确指令/情绪确认），规则引擎直接回答"
        elif complexity == "medium":
            action = "cheap_gate_llm"
            skip_llm = False
            token_budget = config["token_budget_medium"]
            reason = "中等复杂度，便宜门预筛选后调用LLM"
        else:  # high
            action = "direct_llm"
            skip_llm = False
            token_budget = config["token_budget_high"]
            reason = "高复杂度问题（含复杂关键词且较长），直接调用LLM，Token预算上限"
        
        # 3. 估算成本（粗略）
        cost_estimate = token_budget * 0.000001  # 假设每token $0.000001
        
        # 4. 记录路由决策日志
        log_msg = f"便宜门路由决策：问题复杂度={complexity}，选择路径={action}，预估成本=${cost_estimate:.6f}，Token预算={token_budget}"
        self.log(log_msg, "ai")
        
        return {
            "action": action,
            "complexity": complexity,
            "skip_llm": skip_llm,
            "token_budget": token_budget,
            "cost_estimate": cost_estimate,
            "reason": reason,
            "corrected_input": corrected_input if correction_message else user_input,
            "correction_message": correction_message,
        }

    def _check_instructions(self, user_input: str) -> Dict[str, Any]:
        """
        检查是否包含明确指令
        """
        instructions = {
            "开晶": "crystallize",
            "晶体化": "crystallize",
            "系统状态": "status",
            "查看待确认": "show_pending",
            "孔洞花园": "show_holes",
            "确认": "confirm_card",
            "拒绝": "reject_card",
            "暂停自主探测": "pause_auto",
            "恢复自主探测": "resume_auto",
            "归档": "archive"
        }

        for keyword, instruction_type in instructions.items():
            if keyword in user_input:
                return {
                    "direct_match": True,
                    "instruction_type": instruction_type,
                    "matched_keyword": keyword
                }

        return {"direct_match": False}

    def _check_simple_question(self, user_input: str) -> Dict[str, Any]:
        """
        检测是否简单问题（无需LLM）
        """
        simple_patterns = [
            "你好", "hi", "hello", "在吗",
            "谢谢", "感谢", "好的", "OK",
            "知道了", "明白了", "清楚",
            "继续", "接着说", "然后呢"
        ]

        stripped = user_input.strip()
        if len(stripped) < 10:
            for pattern in simple_patterns:
                if pattern in stripped:
                    return {
                        "is_simple": True,
                        "matched_pattern": pattern,
                        "reason": f"匹配简单模式: {pattern}"
                    }

        return {"is_simple": False}

    def _check_search_frequency(self, history: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        检查搜索频率衰减（连续3轮未搜索）
        """
        # 检查最近3轮用户消息是否包含搜索词
        search_keywords = ["搜索", "查找", "找", "查一下", "搜索一下", "外部", "信息"]
        user_messages = [msg[1] for msg in history if msg[0] == "user"]

        if len(user_messages) < 3:
            return {"need_reminder": False, "search_count": 0}

        recent = user_messages[-3:]
        search_count = len([msg for msg in recent if any(kw in msg for kw in search_keywords)])

        return {
            "need_reminder": search_count == 0,
            "search_count": search_count,
            "recent_messages": recent
        }

    def _check_emotion_only(self, user_input: str) -> Dict[str, Any]:
        """
        检测纯情绪表达
        """
        emotion_words = ["哈哈", "呵呵", "呜呜", "唉", "诶", "嗯", "哦", "啊", "哇"]
        stripped = user_input.strip()
        if len(stripped) < 5:
            for word in emotion_words:
                if word in stripped:
                    return {
                        "is_emotion_only": True,
                        "matched_word": word
                    }

        return {"is_emotion_only": False}

    def _estimate_cost(self, user_input: str, history: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        估算Token消耗
        """
        # 估算输入长度
        input_tokens = len(user_input) / 2  # 粗略估算（中文约2字符/token）

        # 估算历史长度
        history_tokens = sum(len(msg[1]) / 2 for msg in history[-8:])

        # 估算输出
        output_tokens = min(500, len(user_input))  # 简单估算

        return {
            "estimated_input_tokens": int(input_tokens + history_tokens),
            "estimated_output_tokens": int(output_tokens),
            "estimated_total_tokens": int(input_tokens + history_tokens + output_tokens),
            "estimated_cost_usd": round((input_tokens + history_tokens + output_tokens) * 0.000001, 6)
        }

    def adjust_search_counter(self, delta: int = 1) -> None:
        """调整搜索计数器：delta=0 表示重置，正整数表示累加。"""
        if delta == 0:
            self._search_counter = 0
        else:
            self._search_counter += int(delta)

