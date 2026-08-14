#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from governance.config import Config
from harness.engine import CrystalEngine

class SVRMADValidator:
    """
    SVR-MAD (Sequential Variance Reduction - Multi-Agent Debate)
    贝叶斯后验验证引擎
    
    论文依据: arXiv:2605.08234
    核心思想: 将辩论前信号作为先验，辩论结果作为后验证据，
    用贝叶斯公式更新每个角色"正确"的后验概率
    """
    
    def __init__(self, engine: 'CrystalEngine' = None):
        self.engine = engine
        self.prior_history: List[Dict] = []
        self._load_prior_history()
    
    def _load_prior_history(self):
        """从 evolution_log 加载先验历史"""
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.prior_history = data.get("events", [])
            except:
                self.prior_history = []
    
    def compute_prior(self, role_name: str, debate_rounds: List[Dict]) -> float:
        """
        计算角色的先验概率（基于历史表现）
        
        先验 = (历史采纳次数 + 1) / (历史总参与次数 + 2)
        采用 Laplace 平滑
        """
        # 从历史中统计该角色的表现
        adopted_count = 0
        total_count = 0
        
        # 从 evolution_log 中统计
        for event in self.prior_history:
            details = event.get("details", {})
            if "role" in details and details["role"] == role_name:
                total_count += 1
                if event.get("event_type") == "verification_passed":
                    adopted_count += 1
        
        # 从当前辩论轮次中统计
        for rd in debate_rounds:
            for ans in rd.get("answers", []):
                if ans.get("role") == role_name:
                    total_count += 1
        
        # Laplace 平滑
        prior = (adopted_count + 1) / (total_count + 2) if total_count > 0 else 0.5
        
        return prior
    
    def compute_likelihood(self, role_name: str, debate_rounds: List[Dict]) -> float:
        """
        计算似然概率（基于本轮辩论表现）
        
        似然 = 证据评分 / 最高分
        """
        # 从最后一轮获取证据评分
        if not debate_rounds:
            return 0.5
        
        last_round = debate_rounds[-1]
        audit = last_round.get("audit", {})
        ev_scores = audit.get("evidence_scores", {})
        
        # 查找该角色的评分
        role_score = 0.0
        for name, score in ev_scores.items():
            if name == role_name:
                role_score = score
                break
        
        # 归一化
        max_score = max(ev_scores.values()) if ev_scores else 1.0
        likelihood = role_score / max_score if max_score > 0 else 0.5
        
        return likelihood
    
    def compute_posterior(self, role_name: str, debate_rounds: List[Dict]) -> float:
        """
        计算后验概率
        
        P(正确 | 证据) = P(证据 | 正确) * P(正确) / P(证据)
        """
        prior = self.compute_prior(role_name, debate_rounds)
        likelihood = self.compute_likelihood(role_name, debate_rounds)
        
        # 归一化常数（简化为 1）
        posterior = prior * likelihood
        
        # 限制范围
        return max(0.0, min(1.0, posterior))
    
    def validate_all_roles(self, debate_rounds: List[Dict]) -> Dict[str, float]:
        """
        验证所有角色，返回后验概率字典
        """
        results = {}
        
        # 收集所有角色
        roles = set()
        for rd in debate_rounds:
            for ans in rd.get("answers", []):
                role = ans.get("role", "")
                if role:
                    roles.add(role)
        
        for role in roles:
            posterior = self.compute_posterior(role, debate_rounds)
            results[role] = posterior
        
        return results
    
    def get_most_reliable_role(self, debate_rounds: List[Dict]) -> Tuple[str, float]:
        """
        返回后验概率最高的角色
        """
        results = self.validate_all_roles(debate_rounds)
        if not results:
            return ("未知", 0.0)
        
        best_role = max(results.items(), key=lambda x: x[1])
        return best_role


# =============================================================================
# 12.3 沙盒执行引擎
# =============================================================================

