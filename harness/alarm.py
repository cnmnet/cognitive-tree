#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from governance.config import Config

class AlarmMonitor:
    """
    八道防线警报系统
    根据配置规则监控辩论过程中的关键指标，触发相应警报
    """

    def __init__(self, rules: dict = None, log_callback=None):
        """
        :param rules: 警报规则字典，若为None则使用 Config.ALARM_RULES
        :param log_callback: 日志回调函数，用于记录警报事件
        """
        self.rules = rules or Config.ALARM_RULES
        self.log = log_callback or (lambda msg, level="system": print(f"[{level.upper()}] {msg}"))
        # 状态跟踪
        self.external_empty_count = 0      # 连续空外部数据计数
        self.jaccard_history = []          # 最近3轮的Jaccard值
        self.alarm_triggered = False       # 本轮是否已触发警报（防止重复）

    def check(self, metrics: dict) -> List[Dict[str, Any]]:
        """
        检查所有警报规则，返回触发的警报列表

        :param metrics: 包含以下键的字典：
            - crystal_reference_rate: float (本轮晶体引用率)
            - bias_amplification: float (本轮偏见强化指数)
            - external_has_new: bool (本轮是否有新外部数据)
            - jaccard_similarity: float (本轮Jaccard相似度)
        :return: 触发的警报列表，每个元素为 dict { 'rule_name', 'message', 'action', 'data' }
        """
        triggered = []
        # 1. 知识贫瘠警报
        if self.rules.get("knowledge_poverty", {}).get("enabled", True):
            threshold = self.rules["knowledge_poverty"]["threshold"]
            if metrics.get("crystal_reference_rate", 1.0) < threshold:
                triggered.append({
                    "rule": "knowledge_poverty",
                    "message": self.rules["knowledge_poverty"]["message"],
                    "action": self.rules["knowledge_poverty"]["action"],
                    "data": {"rate": metrics["crystal_reference_rate"], "threshold": threshold}
                })

        # 2. 偏见膨胀警报
        if self.rules.get("bias_inflation", {}).get("enabled", True):
            threshold = self.rules["bias_inflation"]["threshold"]
            if metrics.get("bias_amplification", 0.0) > threshold:
                triggered.append({
                    "rule": "bias_inflation",
                    "message": self.rules["bias_inflation"]["message"],
                    "action": self.rules["bias_inflation"]["action"],
                    "data": {"bias": metrics["bias_amplification"], "threshold": threshold}
                })

        # 3. 信息枯竭警报（连续3轮无新数据）
        if self.rules.get("information_starvation", {}).get("enabled", True):
            threshold = self.rules["information_starvation"]["threshold"]
            if metrics.get("external_has_new", True):
                self.external_empty_count = 0
            else:
                self.external_empty_count += 1
            if self.external_empty_count >= threshold:
                triggered.append({
                    "rule": "information_starvation",
                    "message": self.rules["information_starvation"]["message"],
                    "action": self.rules["information_starvation"]["action"],
                    "data": {"consecutive_empty": self.external_empty_count, "threshold": threshold}
                })
                self.external_empty_count = 0  # 重置，避免连续触发

        # 4. 思维固化警报（连续3轮Jaccard > 0.8）
        if self.rules.get("thought_stagnation", {}).get("enabled", True):
            threshold = self.rules["thought_stagnation"]["threshold"]
            consecutive = self.rules["thought_stagnation"]["consecutive"]
            jaccard = metrics.get("jaccard_similarity", 0.0)
            self.jaccard_history.append(jaccard)
            if len(self.jaccard_history) > consecutive:
                self.jaccard_history.pop(0)
            if len(self.jaccard_history) == consecutive and all(j > threshold for j in self.jaccard_history):
                triggered.append({
                    "rule": "thought_stagnation",
                    "message": self.rules["thought_stagnation"]["message"],
                    "action": self.rules["thought_stagnation"]["action"],
                    "data": {"jaccards": self.jaccard_history.copy(), "threshold": threshold}
                })
                self.jaccard_history.clear()  # 重置

        # 5. 证据强度警报
        if self.rules.get("evidence_strength", {}).get("enabled", True):
            threshold = self.rules["evidence_strength"]["threshold"]
            if metrics.get("evidence_strength", 1.0) < threshold:
                triggered.append({
                    "rule": "evidence_strength",
                    "message": self.rules["evidence_strength"]["message"],
                    "action": self.rules["evidence_strength"]["action"],
                    "data": {"score": metrics.get("evidence_strength", 1.0), "threshold": threshold}
                })

        # 6. 逻辑一致性警报（论证平衡度）
        if self.rules.get("logic_consistency", {}).get("enabled", True):
            threshold = self.rules["logic_consistency"]["threshold"]
            if metrics.get("logic_consistency", 1.0) < threshold:
                triggered.append({
                    "rule": "logic_consistency",
                    "message": self.rules["logic_consistency"]["message"],
                    "action": self.rules["logic_consistency"]["action"],
                    "data": {"score": metrics.get("logic_consistency", 1.0), "threshold": threshold}
                })

        # 7. 过度推断警报
        if self.rules.get("overreach", {}).get("enabled", True):
            threshold = self.rules["overreach"]["threshold"]
            if metrics.get("overreach_score", 0.0) > threshold:
                triggered.append({
                    "rule": "overreach",
                    "message": self.rules["overreach"]["message"],
                    "action": self.rules["overreach"]["action"],
                    "data": {"score": metrics.get("overreach_score", 0.0), "threshold": threshold}
                })

        # 8. 表达可靠性警报
        if self.rules.get("output_reliability", {}).get("enabled", True):
            threshold = self.rules["output_reliability"]["threshold"]
            if metrics.get("reliability_score", 1.0) < threshold:
                triggered.append({
                    "rule": "output_reliability",
                    "message": self.rules["output_reliability"]["message"],
                    "action": self.rules["output_reliability"]["action"],
                    "data": {"score": metrics.get("reliability_score", 1.0), "threshold": threshold}
                })

        return triggered

    def handle_alarm(self, alarm: Dict, debate_engine) -> bool:
        """
        处理单个警报，执行对应动作，并返回是否应继续辩论

        :param alarm: 警报字典
        :param debate_engine: DebateEngine 实例，用于调用其方法（如注入视角、触发搜索）
        :return: True 表示恢复辩论，False 表示终止辩论（目前始终恢复）
        """
        action = alarm.get("action")
        message = alarm.get("message")

        # 记录事件（由上层调用者写入 evolution_log）
        self.log(f"🚨 {message}", "warning")

        if action == "inject_external":
            # 强制注入外部知识：调用 debate_engine 的外部搜索并注入
            self.log("  执行动作：强制注入外部知识", "system")
            # 我们可以直接调用 debate_engine._fetch_external_overview 并注入到下一轮
            # 但需要暴露接口，我们在 DebateEngine 中添加 _inject_external_knowledge 方法
            debate_engine._inject_external_knowledge(alarm)

        elif action == "review_output":
            # 重审不可靠输出，并用外部知识支撑本轮审计
            self.log("  执行动作：注入外部知识 + 重审不可靠输出", "system")
            debate_engine._inject_external_knowledge(alarm)
            debate_engine._review_unreliable_outputs(alarm)

        elif action == "inject_perspective":
            # 强制注入对立视角：可以在系统消息中加入新角色或提示
            self.log("  执行动作：强制注入对立视角", "system")
            debate_engine._inject_perspective(alarm)

        elif action == "trigger_search":
            # 强制触发外部搜索
            self.log("  执行动作：强制触发外部搜索", "system")
            debate_engine._trigger_search(alarm)

        else:
            self.log(f"  未知动作：{action}，跳过", "warning")

        return True  # 恢复辩论

