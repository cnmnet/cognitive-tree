#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

class RUMADController:
    """
    RUMAD 拓扑控制原型 (基于 Q-learning)
    
    将通信拓扑控制建模为RL问题：
    - 状态：各角色立场向量 + 当前轮次 + 辩论质量
    - 动作：选择下一轮谁对谁发言
    - 奖励：辩论质量提升 (Jaccard 变化 + 审计评分变化)
    
    论文依据: RUMAD (AAMAS 2026, arXiv:2602.23876)
    """
    
    def __init__(self, role_names: List[str], learning_rate: float = 0.1, 
                 discount_factor: float = 0.9, epsilon: float = 0.3):
        """
        初始化 RUMAD 控制器
        
        Args:
            role_names: 角色名称列表
            learning_rate: 学习率 (alpha)
            discount_factor: 折扣因子 (gamma)
            epsilon: 探索率 (epsilon-greedy)
        """
        self.role_names = role_names
        self.n_roles = len(role_names)
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        
        # Q-table: {(state_key): {action_key: q_value}}
        self.q_table = defaultdict(lambda: defaultdict(float))
        
        # 记录状态-动作访问次数（用于调试）
        self.visit_counts = defaultdict(lambda: defaultdict(int))
        
        # 当前辩论状态
        self.current_state = None
        self.last_action = None
        self.last_reward = 0.0
        
        # 历史记录
        self.history = []

        # 用户票选偏好：{角色名: 偏好强度（-0.5 ~ +0.5）}
        self.user_preferences: Dict[str, float] = {}
        
        # 是否启用
        self.enabled = True
        
        self._log("🧠 RUMAD 控制器初始化完成", "system")

    def apply_user_preferences(self, preferences: Dict[str, float]) -> None:
        """吸收用户票选权重，使高票角色在拓扑决策中优先发言。"""
        self.user_preferences = {
            name: max(-0.5, min(0.5, weight))
            for name, weight in preferences.items()
            if name in self.role_names
        }
        if self.user_preferences:
            self._log(f"🧠 RUMAD 已吸收用户票选偏好: {self.user_preferences}", "system")

    def prioritize_roles(self, roles: List[Any]) -> List[Any]:
        """按用户票选偏好稳定排序角色，高票角色在下一场辩论优先调用。"""
        return sorted(roles, key=lambda r: -self.user_preferences.get(r.name, 0.0))
    
    def _log(self, msg: str, level: str = "system"):
        """日志辅助"""
        print(f"[{level.upper()}] {msg}")
    
    def _get_state_key(self, role_vectors: List[float], round_num: int, 
                       quality_score: float) -> str:
        """
        生成状态键
        
        Args:
            role_vectors: 各角色的立场向量 (压缩表示)
            round_num: 当前轮次
            quality_score: 当前辩论质量评分
        
        Returns:
            str: 状态键
        """
        # 将角色向量离散化 (简化为高/中/低)
        discretized = []
        for v in role_vectors[:5]:  # 最多取5个角色
            if v > 0.6:
                discretized.append("H")
            elif v > 0.3:
                discretized.append("M")
            else:
                discretized.append("L")
        
        # 质量等级
        if quality_score > 0.7:
            q_level = "H"
        elif quality_score > 0.4:
            q_level = "M"
        else:
            q_level = "L"
        
        # 轮次等级
        if round_num < 3:
            r_level = "E"  # Early
        elif round_num < 6:
            r_level = "M"  # Mid
        else:
            r_level = "L"  # Late
        
        state = f"{''.join(discretized)}_{q_level}_{r_level}"
        return state
    
    def _get_role_vectors(self, debate_answers: List[Dict]) -> List[float]:
        """
        从辩论回答中提取角色立场向量
        
        Args:
            debate_answers: 各角色的回答列表 [{"role": "激进者", "answer": "..."}]
        
        Returns:
            List[float]: 各角色的立场向量 (简化版: 基于回答长度和关键词)
        """
        vectors = []
        for item in debate_answers:
            answer = item.get("answer", "")
            role = item.get("role", "")
            
            # 简化特征: 回答长度 + 关键词匹配
            length_score = min(1.0, len(answer) / 500)
            
            # 关键词强度
            radical_keywords = ["颠覆", "创新", "突破", "激进", "大胆"]
            conservative_keywords = ["风险", "稳健", "保守", "安全", "验证"]
            
            radical_score = sum(1 for kw in radical_keywords if kw in answer) / len(radical_keywords)
            conservative_score = sum(1 for kw in conservative_keywords if kw in answer) / len(conservative_keywords)
            
            # 综合向量
            if "激进者" in role:
                vector = (length_score + radical_score) / 2
            elif "保守者" in role:
                vector = (length_score + conservative_score) / 2
            else:
                vector = (length_score + max(radical_score, conservative_score)) / 2
            
            vectors.append(min(1.0, max(0.0, vector)))
        
        return vectors
    
    def _get_available_actions(self, round_num: int) -> List[Tuple[str, str]]:
        """
        获取当前轮次可用的动作
        
        Args:
            round_num: 当前轮次
        
        Returns:
            List[Tuple[str, str]]: 可用动作列表 (发言者, 目标)
        """
        actions = []
        
        # 前3轮: 所有角色都可以发言，但有限制
        if round_num <= 3:
            # 每个角色都可以发言，但目标只能是其他角色
            for i, speaker in enumerate(self.role_names):
                for j, target in enumerate(self.role_names):
                    if i != j:
                        actions.append((speaker, target))
        else:
            # 后续轮次: 只选择前一轮表现较好的角色
            # 简化: 所有角色都可以发言
            for i, speaker in enumerate(self.role_names):
                for j, target in enumerate(self.role_names):
                    if i != j:
                        actions.append((speaker, target))
        
        # 限制动作数量 (前5个)
        return actions[:10] if len(actions) > 10 else actions
    
    def select_action(self, state_key: str, available_actions: List[Tuple[str, str]],
                      round_num: int) -> Optional[Tuple[str, str]]:
        """使用 epsilon-greedy 策略选择动作（前3轮warm-up除外）"""
        if not available_actions or not self.enabled:
            return None

        # ===== 修改：前3轮不做 RUMAD 决策（warm-up），直接随机 =====
        if round_num <= 3:
            pool = available_actions[:5]
            weights = [1.0 + self.user_preferences.get(a[0], 0.0) * 3.0 for a in pool]
            action = random.choices(pool, weights=weights, k=1)[0]
            if hasattr(self, '_log'):
                self._log(f"  🌡️ RUMAD warm-up 第 {round_num} 轮，偏好加权选择 {action[0]} -> {action[1]}", "system")
            return action

        # epsilon-greedy
        if random.random() < self.epsilon:
            action = random.choice(available_actions)
            self._log(f"  🎲 RUMAD 探索: {action[0]} -> {action[1]}", "system")
            return action

        # 利用：选择Q值最高的动作
        best_action = None
        best_q = -float('inf')
        for action in available_actions:
            action_key = f"{action[0]}->{action[1]}"
            q_value = self.q_table[state_key].get(action_key, 0.0)
            q_value += self.user_preferences.get(action[0], 0.0) * 0.5
            if q_value > best_q:
                best_q = q_value
                best_action = action

        if best_action:
            self._log(f"  📊 RUMAD 利用: {best_action[0]} -> {best_action[1]} (Q={best_q:.3f})", "system")

        return best_action
    
    def update_q_value(self, state_key: str, action: Tuple[str, str], 
                        reward: float, next_state_key: str) -> None:
        """
        更新 Q 值
        
        Args:
            state_key: 当前状态键
            action: 执行的动作
            reward: 获得的奖励
            next_state_key: 下一个状态键
        """
        action_key = f"{action[0]}->{action[1]}"
        
        # 当前 Q 值
        current_q = self.q_table[state_key].get(action_key, 0.0)
        
        # 下一个状态的最大 Q 值
        next_max_q = max(self.q_table[next_state_key].values()) if self.q_table[next_state_key] else 0.0
        
        # Q-learning 更新公式
        new_q = current_q + self.lr * (reward + self.gamma * next_max_q - current_q)
        
        # 更新 Q-table
        self.q_table[state_key][action_key] = new_q
        self.visit_counts[state_key][action_key] += 1
    
    def compute_reward(self, previous_answers: List[Dict], current_answers: List[Dict],
                       previous_audit: Dict, current_audit: Dict) -> float:
        """
        计算奖励（使用 evidence_scores 平均值）
        论文依据: SVR-MAD 贝叶斯后验验证
        """
        reward = 0.0

        # 1. Jaccard 相似度变化（保留）
        def get_jaccard(answers):
            if len(answers) < 2:
                return 0.5
            texts = [a.get("answer", "") for a in answers]
            if len(texts) >= 2:
                import re
                def tokens(text):
                    return set(re.findall(r'[\u4e00-\u9fff]{2,}', text))
                token_sets = [tokens(t) for t in texts if t]
                if len(token_sets) >= 2:
                    sims = []
                    for i in range(len(token_sets)):
                        for j in range(i + 1, len(token_sets)):
                            if token_sets[i] and token_sets[j]:
                                inter = len(token_sets[i] & token_sets[j])
                                union = len(token_sets[i] | token_sets[j])
                                sims.append(inter / union if union > 0 else 0.5)
                    return sum(sims) / len(sims) if sims else 0.5
                return 0.5
            return 0.5

        prev_jaccard = get_jaccard(previous_answers) if previous_answers else 0.5
        curr_jaccard = get_jaccard(current_answers) if current_answers else 0.5
        jaccard_delta = prev_jaccard - curr_jaccard
        reward += jaccard_delta * 0.4

        # ===== 核心修改：使用 evidence_scores 平均值替代文本长度方差 =====
        # 2. 证据评分变化（来自审计员）
        prev_score = previous_audit.get("evidence_scores", {}) if previous_audit else {}
        curr_score = current_audit.get("evidence_scores", {}) if current_audit else {}

        prev_avg = sum(prev_score.values()) / len(prev_score) if prev_score else 0.5
        curr_avg = sum(curr_score.values()) / len(curr_score) if curr_score else 0.5

        # 评分提升 → 正奖励，评分下降 → 负奖励
        score_delta = curr_avg - prev_avg

        # ===== Day 6 优化：增加审计置信度乘数 =====
        confidence_multiplier = 1.0
        if current_audit:
            summary = current_audit.get("summary", "")
            if "证据不足" in summary or "待补充" in summary or "暂缓" in summary:
                confidence_multiplier = 0.5
                self._log(f"  ⚠️ 审计置信度较低，奖励权重降至 {confidence_multiplier}", "system")

        reward += score_delta * 0.4 * confidence_multiplier

        # 3. 多样性奖励（保留，但权重降低）
        if current_answers:
            vectors = self._get_role_vectors(current_answers)
            if len(vectors) > 1:
                diversity = 0.0
                for i in range(len(vectors)):
                    for j in range(i + 1, len(vectors)):
                        diversity += abs(vectors[i] - vectors[j])
                diversity = diversity / (len(vectors) * (len(vectors) - 1) / 2) if len(vectors) > 1 else 0
                reward += diversity * 0.2

        # 限制范围
        return max(-1.0, min(1.0, reward))
    
    def get_topology_decision(self, debate_answers: List[Dict], 
                             round_num: int, 
                             audit_result: Dict = None) -> Optional[Tuple[str, str]]:
        """
        获取拓扑决策 (对外接口)
        
        Args:
            debate_answers: 当前轮各角色的回答
            round_num: 当前轮次
            audit_result: 审计结果
        
        Returns:
            Optional[Tuple[str, str]]: (发言者, 目标角色)
        """
        if not self.enabled or not debate_answers:
            return None
        
        # 提取角色向量
        role_vectors = self._get_role_vectors(debate_answers)
        
        # 计算质量评分
        quality_score = 0.5
        if audit_result:
            scores = audit_result.get("evidence_scores", {})
            if scores:
                quality_score = sum(scores.values()) / len(scores)
        
        # 生成状态键
        state_key = self._get_state_key(role_vectors, round_num, quality_score)
        self.current_state = state_key
        
        # 获取可用动作
        available_actions = self._get_available_actions(round_num)
        
        # 选择动作
        action = self.select_action(state_key, available_actions, round_num)
        
        if action:
            self.last_action = action
            # 记录历史
            self.history.append({
                "round": round_num,
                "state": state_key,
                "action": action,
                "quality": quality_score
            })
        
        return action
    
    def update_with_result(self, previous_answers: List[Dict], 
                          current_answers: List[Dict],
                          previous_audit: Dict,
                          current_audit: Dict) -> None:
        """
        用辩论结果更新 Q-learning
        
        Args:
            previous_answers: 上一轮回答
            current_answers: 当前轮回答
            previous_audit: 上一轮审计
            current_audit: 当前轮审计
        """
        if not self.last_action or not self.current_state:
            return
        
        # 计算奖励
        reward = self.compute_reward(previous_answers, current_answers, 
                                     previous_audit, current_audit)
        self.last_reward = reward
        
        # 获取下一个状态
        role_vectors = self._get_role_vectors(current_answers)
        quality_score = 0.5
        if current_audit:
            scores = current_audit.get("evidence_scores", {})
            if scores:
                quality_score = sum(scores.values()) / len(scores)
        
        next_state = self._get_state_key(role_vectors, len(self.history), quality_score)
        
        # 更新 Q 值
        self.update_q_value(self.current_state, self.last_action, reward, next_state)
        
        self._log(f"  📈 RUMAD 更新: 奖励={reward:.3f}, 状态={self.current_state[:20]}...", "system")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取 RUMAD 统计信息"""
        total_visits = sum(sum(vals.values()) for vals in self.visit_counts.values())
        
        return {
            "enabled": self.enabled,
            "total_actions": len(self.history),
            "q_table_size": len(self.q_table),
            "total_visits": total_visits,
            "epsilon": self.epsilon,
            "learning_rate": self.lr,
            "last_action": self.last_action,
            "last_reward": self.last_reward,
            "history": self.history[-10:]  # 最近10条
        }
    
    def set_enabled(self, enabled: bool) -> None:
        """启用或禁用 RUMAD 拓扑控制，并记录状态日志。"""
        self.enabled = bool(enabled)
        self._log("🧠 RUMAD 已启用" if self.enabled else "🧠 RUMAD 已禁用", "system")
    
    def reset(self):
        """重置 RUMAD 状态"""
        self.q_table.clear()
        self.visit_counts.clear()
        self.history.clear()
        self.current_state = None
        self.last_action = None
        self.last_reward = 0.0
        self._log("🧠 RUMAD 已重置", "system")
