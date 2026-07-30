#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 5 测试：验证门控Hebbian学习
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import Config, FileIO, CrystalEngine, Crystal

def test_hebbian():
    print("🧪 Day 5 测试：Hebbian 学习权重更新与排序影响")
    
    # 临时禁用向量检索，确保使用 BM25
    original_vector_enabled = Config.VECTOR_SEARCH_ENABLED
    Config.VECTOR_SEARCH_ENABLED = False
    
    try:
        engine = CrystalEngine(FileIO())
        
        # 准备测试晶体（确保晶体内容有足够的关键词差异）
        crystals = [
            Crystal(id="C001", content="决策质量提升方法：引入多角色辩论机制"),
            Crystal(id="C002", content="团队协作效率：建立快速反馈循环"),
            Crystal(id="C003", content="预算管理优化：实施滚动预测模型"),
        ]
        
        # 模拟更新权重
        engine.update_hebbian_weights(["C001", "C002"], "decision", 0.8)
        engine.update_hebbian_weights(["C002", "C003"], "decision", 0.6)
        
        # 获取加成
        boost1 = engine.get_hebbian_boost("C001", "decision")
        boost2 = engine.get_hebbian_boost("C002", "decision")
        boost3 = engine.get_hebbian_boost("C003", "decision")
        print(f"C001 boost: {boost1:.2f}")
        print(f"C002 boost: {boost2:.2f}")
        print(f"C003 boost: {boost3:.2f}")
        
        # 检查排序影响
        query = "决策"
        ranked = engine.rank_crystals(query, crystals, top_k=3, task_type="decision")
        
        print("排序结果（按分数）：")
        if not ranked:
            print("  ❌ 没有返回任何结果")
            return False
            
        for score, c in ranked:
            print(f"  {c.id}: {score:.2f}")
        
        # 验证 C001 应该排在最前（因为与C002有高权重对，且任务匹配）
        if ranked[0][1].id == "C001":
            print("✅ C001 排名第一，Hebbian 加成生效")
            return True
        else:
            print(f"❌ C001 未排第一（实际第一名是 {ranked[0][1].id}），检查权重")
            return False
            
    finally:
        # 恢复向量检索配置
        Config.VECTOR_SEARCH_ENABLED = original_vector_enabled

if __name__ == "__main__":
    success = test_hebbian()
    sys.exit(0 if success else 1)