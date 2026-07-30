#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SVR-MAD 贝叶斯后验验证 (Day 12)
将辩论前信号作为先验，辩论结果作为后验证据，用贝叶斯公式更新每个角色"正确"的后验概率

论文依据: SVR-MAD (arXiv:2605.08234) - Token成本最高降低61%
"""

import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from crystal_tree_all_in_one_day import Config, FileIO
except ImportError:
    from ..crystal_tree_all_in_one_day import Config, FileIO


class SVRMADValidator:
    """
    SVR-MAD 贝叶斯后验验证器
    
    使用贝叶斯公式更新每个角色的后验正确概率。
    先验：基于角色历史胜率（从突触文件获取）
    似然：基于本轮辩论中的表现（审计评分）
    """
    
    def __init__(self, engine=None, log_callback=None):
        self.engine = engine
        self.log = log_callback or print
    
    def compute_posterior(
        self,
        role_names: List[str],
        prior_probs: Dict[str, float],
        likelihoods: Dict[str, float]
    ) -> Dict[str, float]:
        """
        计算后验概率
        
        Args:
            role_names: 角色名称列表
            prior_probs: 先验概率 {角色名: 概率}
            likelihoods: 似然度 {角色名: 似然值}
        
        Returns:
            {角色名: 后验概率}
        """
        # 计算证据（边际似然）
        evidence = 0.0
        for name in role_names:
            prior = prior_probs.get(name, 0.5)
            likelihood = likelihoods.get(name, 0.5)
            evidence += prior * likelihood
        
        if evidence == 0:
            # 如果证据为0，返回均匀分布
            return {name: 1.0 / len(role_names) for name in role_names}
        
        # 计算后验
        posterior = {}
        for name in role_names:
            prior = prior_probs.get(name, 0.5)
            likelihood = likelihoods.get(name, 0.5)
            posterior[name] = (prior * likelihood) / evidence
        
        return posterior
    
    def get_prior_from_history(self, role_key_map: Dict[str, str]) -> Dict[str, float]:
        """
        从历史突触数据获取先验概率
        
        Args:
            role_key_map: {角色名: 角色key}
        
        Returns:
            {角色名: 先验概率}
        """
        prior = {}
        
        # 尝试从突触文件加载
        synapse_file = Config.DATA_ROOT / "系统日志" / "角色突触.json"
        if synapse_file.exists():
            try:
                with open(synapse_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                for role_name, role_key in role_key_map.items():
                    role_data = data.get(role_key, {})
                    win_count = role_data.get("win_count", 0)
                    loss_count = role_data.get("loss_count", 0)
                    total = win_count + loss_count
                    if total > 0:
                        prior[role_name] = win_count / total
                    else:
                        prior[role_name] = 0.5
            except Exception as e:
                self.log(f"⚠️ 加载突触数据失败: {e}")
                for name in role_key_map:
                    prior[name] = 0.5
        else:
            for name in role_key_map:
                prior[name] = 0.5
        
        return prior
    
    def compute_likelihood_from_audit(
        self,
        audit_result: Dict,
        role_names: List[str]
    ) -> Dict[str, float]:
        """
        从审计结果计算似然度
        
        Args:
            audit_result: 审计结果
            role_names: 角色名称列表
        
        Returns:
            {角色名: 似然度}
        """
        likelihood = {}
        
        # 从审计评分获取
        evidence_scores = audit_result.get("evidence_scores", {})
        
        for name in role_names:
            # 尝试多种可能的键名
            score = evidence_scores.get(name, 0.5)
            if score == 0.5:
                # 尝试匹配角色名
                for key, val in evidence_scores.items():
                    if name in key or key in name:
                        score = val
                        break
            
            # 确保在合理范围内
            likelihood[name] = max(0.1, min(0.99, float(score)))
        
        # 如果没有评分数据，使用默认值
        if not likelihood:
            for name in role_names:
                likelihood[name] = 0.5
        
        return likelihood
    
    def compute_posterior_for_debate(
        self,
        debate_result: Dict,
        role_key_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        为辩论结果计算后验概率
        
        Returns:
            {
                "posterior": {角色名: 后验概率},
                "prior": {角色名: 先验概率},
                "likelihood": {角色名: 似然度},
                "summary": str,
                "top_role": str,
                "confidence_gap": float
            }
        """
        # 提取角色名称
        role_names = list(role_key_map.keys())
        
        # 获取先验
        prior = self.get_prior_from_history(role_key_map)
        for name in role_names:
            if name not in prior:
                prior[name] = 0.5
        
        # 获取本轮审计结果
        rounds_data = debate_result.get("rounds", [])
        if not rounds_data:
            return {
                "posterior": {name: 1.0 / len(role_names) for name in role_names},
                "prior": prior,
                "likelihood": {name: 0.5 for name in role_names},
                "summary": "无辩论数据，使用均匀分布",
                "top_role": "未知",
                "confidence_gap": 0.0
            }
        
        # 使用最后一轮或指定轮的审计
        last_round = rounds_data[-1]
        audit = last_round.get("audit", {})
        likelihood = self.compute_likelihood_from_audit(audit, role_names)
        
        # 计算后验
        posterior = self.compute_posterior(role_names, prior, likelihood)
        
        # 找出最高概率的角色
        top_role = max(posterior.items(), key=lambda x: x[1])[0]
        
        # 计算置信度差距（最高-第二高）
        sorted_probs = sorted(posterior.values(), reverse=True)
        confidence_gap = sorted_probs[0] - sorted_probs[1] if len(sorted_probs) > 1 else 1.0
        
        # 生成摘要
        summary = f"后验更新完成：{top_role} 以 {posterior[top_role]:.2%} 的概率成为最可信角色"
        
        # 记录到进化日志
        self._log_evolution(debate_result, top_role, posterior, confidence_gap)
        
        return {
            "posterior": posterior,
            "prior": prior,
            "likelihood": likelihood,
            "summary": summary,
            "top_role": top_role,
            "confidence_gap": round(confidence_gap, 3)
        }
    
    def _log_evolution(self, debate_result: Dict, top_role: str, posterior: Dict, gap: float):
        """记录进化事件"""
        if self.engine and hasattr(self.engine, 'log_evolution_event'):
            self.engine.log_evolution_event(
                "svr_mad_update",
                {
                    "top_role": top_role,
                    "posterior": posterior,
                    "confidence_gap": gap,
                    "trigger": "debate_complete"
                }
            )
    
    def get_role_key_map(self, debate_result: Dict) -> Dict[str, str]:
        """从辩论结果提取角色名到key的映射"""
        mapping = {
            "激进者": "radical",
            "保守者": "conservative",
            "结构主义者": "structural",
            "百灵鸟": "lark",
            "取经者": "pilgrim",
            "奇谋者": "strategist",
            "延安智者": "statesman",
            "大法官": "judge",
            "首席发言人": "spokesperson",
            "替身-我": "twin"
        }
        
        # 从辩论中提取实际出现的角色
        result = {}
        for rd in debate_result.get("rounds", []):
            for answer in rd.get("answers", []):
                role_name = answer.get("role", "")
                if role_name and role_name not in result:
                    # 尝试找到对应的key
                    key = mapping.get(role_name)
                    if key:
                        result[role_name] = key
                    else:
                        # 尝试通过名称匹配
                        for name, key in mapping.items():
                            if name in role_name or role_name in name:
                                result[role_name] = key
                                break
                        else:
                            # 使用小写化名作为key
                            result[role_name] = role_name.lower().replace(" ", "_")
        
        # 确保至少有一些角色
        if not result:
            result = {
                "激进者": "radical",
                "保守者": "conservative",
                "结构主义者": "structural"
            }
        
        return result


def main():
    """命令行测试"""
    print("=" * 60)
    print("📊 SVR-MAD 贝叶斯后验验证测试")
    print("=" * 60)
    
    validator = SVRMADValidator()
    
    # 模拟数据
    role_names = ["激进者", "保守者", "结构主义者"]
    prior = {
        "激进者": 0.3,
        "保守者": 0.6,
        "结构主义者": 0.4
    }
    likelihood = {
        "激进者": 0.85,
        "保守者": 0.70,
        "结构主义者": 0.75
    }
    
    print("\n先验概率:")
    for name, prob in prior.items():
        print(f"  {name}: {prob:.2%}")
    
    print("\n似然度:")
    for name, prob in likelihood.items():
        print(f"  {name}: {prob:.2%}")
    
    # 计算后验
    posterior = validator.compute_posterior(role_names, prior, likelihood)
    
    print("\n后验概率:")
    for name, prob in posterior.items():
        print(f"  {name}: {prob:.2%}")
    
    # 验证总和为1
    total = sum(posterior.values())
    print(f"\n总和: {total:.4f} (应为1.0)")
    
    print("\n" + "=" * 60)
    print("✅ SVR-MAD 测试完成")


if __name__ == "__main__":
    main()