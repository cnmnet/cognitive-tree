#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 2.8 测试：元问题分类器
"""

import sys
import os

# 添加核心配置目录到 sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
core_config_dir = os.path.join(project_root, "晶体树文件夹", "核心配置")
sys.path.append(core_config_dir)

from question_classifier import QuestionClassifier

def test_classifier():
    print("🧪 Day 2.8 测试：元问题分类器")
    classifier = QuestionClassifier()

    test_cases = [
        ("什么是认知晶体树？", "fact_query"),
        ("我应该选A方案还是B方案？", "decision_dilemma"),
        ("给我一些提升团队效率的想法", "creative_inspiration"),
        ("我这样想对不对？", "reflective_deepening"),
        ("今天天气怎么样？", "unknown"),  # 简单问候归为unknown
        ("如何设计一个OKR体系？", "fact_query"),  # 归为方法查询
        ("选择敏捷还是瀑布？", "decision_dilemma"),
        ("有哪些创新的项目管理方法？", "creative_inspiration"),
        ("我的决策是否合理？", "reflective_deepening"),
    ]

    passed = 0
    for question, expected in test_cases:
        result = classifier.classify(question)
        qtype = result["type"]
        label = result["label"]
        path = result["path"]
        print(f"问题: {question[:30]}...")
        print(f"  分类: {qtype} (期望: {expected}) → 路径: {path}, 标签: {label}")
        if qtype == expected:
            print("  ✅ 匹配")
            passed += 1
        else:
            print(f"  ❌ 预期 {expected}，实际 {qtype}")

    print(f"\n通过 {passed}/{len(test_cases)} 个测试用例")
    return passed == len(test_cases)

if __name__ == "__main__":
    success = test_classifier()
    sys.exit(0 if success else 1)