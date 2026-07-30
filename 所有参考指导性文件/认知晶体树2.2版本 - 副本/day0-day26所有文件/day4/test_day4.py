#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 4 测试：非马尔可夫历史检索 + 失败轨迹记录
"""

import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import Config, FileIO, CrystalEngine, MetaLayer, DebateEngine, AIClient

def test_history_retrieval():
    """测试历史检索功能"""
    print("🧪 Day 4 测试：非马尔可夫历史检索")
    
    # 初始化
    FileIO.ensure_directories()
    files = FileIO()
    engine = CrystalEngine(files)
    
    # 1. 模拟记录一条失败轨迹（写入 evolution_log）
    print("\n📝 步骤1：记录失败轨迹...")
    engine.log_evolution_event(
        "failure_trace",
        {
            "failure_traces": {
                "question": "如何在不增加预算的前提下提升团队技术决策质量？",
                "failure_type": "low_crystal_reference",
                "effective_crystals": ["C001", "C010", "C038"]
            },
            "question": "如何在不增加预算的前提下提升团队技术决策质量？",
            "effective_crystals": ["C001", "C010", "C038"],
            "trigger": "test"
        }
    )
    print("   ✅ 失败轨迹已记录")
    
    # 2. 等待文件写入
    time.sleep(0.5)
    
    # 3. 测试历史检索
    print("\n🔍 步骤2：测试历史检索...")
    meta = MetaLayer(engine, files)
    
    # 当前问题（与历史问题相似）
    current_question = "如何在不增加预算的前提下提升20人研发团队的技术决策质量？"
    result = meta.diagnose_history(current_question, threshold=0.7)
    
    print(f"   匹配结果: {'✅ 匹配成功' if result.get('matched') else '❌ 无匹配'}")
    if result.get("matched"):
        print(f"   相似度: {result.get('match_score', 0):.2f}")
        print(f"   晶体组合: {result.get('crystal_combination', [])}")
        print(f"   历史问题: {result.get('matched_question', '')[:50]}...")
    else:
        print(f"   最佳相似度: {result.get('match_score', 0):.2f}")
    
    # 4. 测试不相似的问题（应不匹配）
    print("\n🔍 步骤3：测试不相似问题（应不匹配）...")
    unrelated = "今天天气怎么样？"
    result2 = meta.diagnose_history(unrelated, threshold=0.7)
    print(f"   匹配结果: {'✅ 匹配成功' if result2.get('matched') else '❌ 无匹配（符合预期）'}")
    
    # 5. 验收
    passed = result.get("matched") and result.get("crystal_combination") and not result2.get("matched")
    
    print("\n" + "=" * 60)
    if passed:
        print("✅ Day 4 测试通过！历史检索功能正常，能复用经验晶体。")
    else:
        print("❌ Day 4 测试失败，请检查以下问题：")
        if not result.get("matched"):
            print("   - 历史检索未匹配到相似问题")
        if not result.get("crystal_combination"):
            print("   - 未能提取有效晶体组合")
    print("=" * 60)
    
    return passed

if __name__ == "__main__":
    success = test_history_retrieval()
    sys.exit(0 if success else 1)