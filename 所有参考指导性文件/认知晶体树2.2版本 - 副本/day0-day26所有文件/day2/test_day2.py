#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 2 测试：便宜门动态路由决策器
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import Config, FileIO, CrystalEngine, CheapGate

def test_routing():
    print("🧪 Day 2 测试：便宜门动态路由")
    
    engine = CrystalEngine(FileIO())
    gate = CheapGate(engine, FileIO())
    
    test_cases = [
        ("你好", "simple"),
        ("谢谢", "simple"),
        ("今天天气怎么样？", "simple"),
        ("如何提升团队效率？", "medium"),
        ("如何在不增加预算的前提下，提升一个20人研发团队的技术决策质量？", "high"),
        ("设计一个自我修正的OKR体系", "high"),
        ("什么是认知晶体树？", "medium"),   # 长度22，无复杂关键词，应为medium
    ]
    
    passed = 0
    for user_input, expected in test_cases:
        result = gate.check(user_input, [])
        complexity = result["complexity"]
        action = result["action"]
        print(f"输入: {user_input[:30]}... 复杂度: {complexity}, 动作: {action}")
        if complexity == expected:
            print(f"  ✅ 预期复杂度 {expected} 匹配")
            passed += 1
        else:
            print(f"  ❌ 预期 {expected}，实际 {complexity}")
    
    print(f"\n通过 {passed}/{len(test_cases)} 个测试用例")
    return passed == len(test_cases)

if __name__ == "__main__":
    success = test_routing()
    sys.exit(0 if success else 1)