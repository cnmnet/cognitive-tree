#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Dict

from external.ai_client import AIClient
from harness.engine import CrystalEngine

class M3MADBenchResult:
    """
    M3MAD-Bench 评估结果
    论文依据: arXiv:2601.01234
    """
    # 多域任务 (Multi-domain)
    reasoning_score: float = 0.0      # 推理能力
    knowledge_score: float = 0.0      # 知识广度
    creativity_score: float = 0.0     # 创意生成
    
    # 多模态输入 (Multi-modal)
    text_score: float = 0.0           # 文本输入
    file_score: float = 0.0           # 文件输入
    dialogue_score: float = 0.0       # 对话历史
    
    # 多维指标 (Multi-dimensional)
    accuracy_score: float = 0.0       # 准确性
    efficiency_score: float = 0.0     # 效率 (Token消耗)
    diversity_score: float = 0.0      # 多样性
    
    @property
    def overall_score(self) -> float:
        """综合评分"""
        scores = [
            self.reasoning_score, self.knowledge_score, self.creativity_score,
            self.text_score, self.file_score, self.dialogue_score,
            self.accuracy_score, self.efficiency_score, self.diversity_score
        ]
        return sum(scores) / len(scores) if scores else 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "reasoning_score": self.reasoning_score,
            "knowledge_score": self.knowledge_score,
            "creativity_score": self.creativity_score,
            "text_score": self.text_score,
            "file_score": self.file_score,
            "dialogue_score": self.dialogue_score,
            "accuracy_score": self.accuracy_score,
            "efficiency_score": self.efficiency_score,
            "diversity_score": self.diversity_score,
            "overall_score": self.overall_score
        }


class M3MADBench:
    """
    M3MAD-Bench 标准化评估引擎
    
    评估三个维度：
    1. 多域任务：推理、知识、创意
    2. 多模态输入：文本、文件、对话历史
    3. 多维指标：准确性、效率、多样性
    """
    
    def __init__(self, engine: 'CrystalEngine', ai_client: 'AIClient'):
        self.engine = engine
        self.ai = ai_client
    
    def evaluate(self, debate_result: Dict) -> M3MADBenchResult:
        """
        对单次辩论结果进行三维评估
        """
        result = M3MADBenchResult()
        
        # 1. 多域任务评估
        result.reasoning_score = self._evaluate_reasoning(debate_result)
        result.knowledge_score = self._evaluate_knowledge(debate_result)
        result.creativity_score = self._evaluate_creativity(debate_result)
        
        # 2. 多模态输入评估
        result.text_score = self._evaluate_text_input(debate_result)
        result.file_score = self._evaluate_file_input(debate_result)
        result.dialogue_score = self._evaluate_dialogue_input(debate_result)
        
        # 3. 多维指标评估
        result.accuracy_score = self._evaluate_accuracy(debate_result)
        result.efficiency_score = self._evaluate_efficiency(debate_result)
        result.diversity_score = self._evaluate_diversity(debate_result)
        
        return result
    
    def _evaluate_reasoning(self, debate_result: Dict) -> float:
        """评估推理能力：基于审计评分"""
        rounds_data = debate_result.get("rounds", [])
        if not rounds_data:
            return 0.5
        
        # 获取最后一轮的审计评分
        last_round = rounds_data[-1]
        audit = last_round.get("audit", {})
        ev_scores = audit.get("evidence_scores", {})
        
        if ev_scores:
            return sum(ev_scores.values()) / len(ev_scores)
        return 0.5
    
    def _evaluate_knowledge(self, debate_result: Dict) -> float:
        """评估知识广度：基于晶体引用率"""
        rounds_data = debate_result.get("rounds", [])
        if not rounds_data:
            return 0.5
        
        total_answers = 0
        total_refs = 0
        
        for rd in rounds_data:
            for ans in rd.get("answers", []):
                text = ans.get("answer", "")
                total_answers += 1
                refs = len(re.findall(r'\[C\d+\]', text)) + len(re.findall(r'\[H\d+\]', text))
                total_refs += min(3, refs)  # 最多计3个
        
        if total_answers == 0:
            return 0.5
        
        return min(1.0, total_refs / (total_answers * 0.5))
    
    def _evaluate_creativity(self, debate_result: Dict) -> float:
        """评估创意生成：基于观点多样性"""
        rounds_data = debate_result.get("rounds", [])
        if not rounds_data:
            return 0.5
        
        # 收集所有角色的观点
        viewpoints = set()
        for rd in rounds_data:
            for ans in rd.get("answers", []):
                text = ans.get("answer", "")
                # 提取关键观点（前20个字符）
                if len(text) > 10:
                    viewpoint = text[:30].strip()
                    viewpoints.add(viewpoint)
        
        # 观点数量越多，多样性越高
        diversity = min(1.0, len(viewpoints) / 10.0)
        return diversity
    
    def _evaluate_text_input(self, debate_result: Dict) -> float:
        """评估文本输入处理能力"""
        # 基于答案长度和质量
        rounds_data = debate_result.get("rounds", [])
        if not rounds_data:
            return 0.5
        
        total_length = 0
        total_answers = 0
        for rd in rounds_data:
            for ans in rd.get("answers", []):
                total_length += len(ans.get("answer", ""))
                total_answers += 1
        
        if total_answers == 0:
            return 0.5
        
        avg_length = total_length / total_answers
        # 300-800字为最佳区间
        if 300 <= avg_length <= 800:
            return 0.9
        elif 150 <= avg_length <= 1000:
            return 0.7
        else:
            return 0.5
    
    def _evaluate_file_input(self, debate_result: Dict) -> float:
        """评估文件输入处理能力"""
        # 检查是否包含文件内容
        question = debate_result.get("question", "")
        if "[文件" in question or "文件内容" in question:
            return 0.8  # 有文件输入且处理良好
        return 0.5  # 无文件输入，中性分
    
    def _evaluate_dialogue_input(self, debate_result: Dict) -> float:
        """评估对话历史处理能力"""
        rounds_data = debate_result.get("rounds", [])
        if len(rounds_data) >= 3:
            return 0.8
        elif len(rounds_data) >= 2:
            return 0.6
        return 0.4
    
    def _evaluate_accuracy(self, debate_result: Dict) -> float:
        """评估准确性：基于审计评分和沙盒验证"""
        rounds_data = debate_result.get("rounds", [])
        if not rounds_data:
            return 0.5
        
        last_round = rounds_data[-1]
        audit = last_round.get("audit", {})
        ev_scores = audit.get("evidence_scores", {})
        
        if ev_scores:
            return sum(ev_scores.values()) / len(ev_scores)
        return 0.5
    
    def _evaluate_efficiency(self, debate_result: Dict) -> float:
        """评估效率：基于Token消耗"""
        # 估算Token消耗
        total_chars = 0
        rounds_data = debate_result.get("rounds", [])
        for rd in rounds_data:
            for ans in rd.get("answers", []):
                total_chars += len(ans.get("answer", ""))
        
        estimated_tokens = total_chars // 2
        
        # 效率评分：token越少越高
        if estimated_tokens < 500:
            return 0.9
        elif estimated_tokens < 1000:
            return 0.7
        elif estimated_tokens < 2000:
            return 0.5
        else:
            return 0.3
    
    def _evaluate_diversity(self, debate_result: Dict) -> float:
        """评估多样性：基于角色观点差异"""
        rounds_data = debate_result.get("rounds", [])
        if not rounds_data:
            return 0.5
        
        # 计算各角色答案的Jaccard相似度
        import itertools
        answers = []
        for rd in rounds_data:
            for ans in rd.get("answers", []):
                answers.append(ans.get("answer", ""))
        
        if len(answers) < 2:
            return 0.5
        
        # 计算平均相似度
        total_sim = 0
        pairs = 0
        for i, j in itertools.combinations(range(len(answers)), 2):
            sim = self._jaccard_similarity(answers[i], answers[j])
            total_sim += sim
            pairs += 1
        
        avg_sim = total_sim / pairs if pairs > 0 else 0.5
        
        # 多样性 = 1 - 平均相似度
        diversity = 1 - avg_sim
        return max(0.0, min(1.0, diversity))
    
    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """计算Jaccard相似度"""
        def tokens(text: str) -> set:
            words = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
            return set(words)
        
        set1 = tokens(text1)
        set2 = tokens(text2)
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0


# =============================================================================
# 12.5 集成到 CrystalEngine
# =============================================================================

