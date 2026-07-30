#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 2.5 测试：认知风格分析
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import FileIO, CrystalEngine, CognitiveFingerprint

def test_style_analysis():
    print("🧪 Day 2.5 测试：认知风格分析")
    
    engine = CrystalEngine(FileIO())
    extractor = engine.fingerprint_extractor
    
    # 模拟两种不同用户的对话历史
    history_deductive = [
        ("user", "根据逻辑推导，我们应该先做A，因为根据原则X，A是必然选择。"),
        ("user", "从数据分析来看，结论B是正确的。"),
        ("user", "因此，我建议采用方案C。"),
        ("user", "数据表明，这样做效率最高。"),
        ("user", "所以，最终决定是D。"),
    ]
    
    history_inductive = [
        ("user", "我观察了很多案例，发现模式Y很常见。"),
        ("user", "例如，在项目A中，他们用了方法B成功。"),
        ("user", "又比如，在行业C中，类似方法也有效。"),
        ("user", "这些例子让我想到，我们可以尝试。"),
        ("user", "我觉得这种方法可能适合我们。"),
    ]
    
    # 提取风格
    fp_ded = extractor.extract(history_deductive)
    fp_ind = extractor.extract(history_inductive)
    
    ops_ded = extractor.get_cognitive_operators(fp_ded)
    ops_ind = extractor.get_cognitive_operators(fp_ind)
    
    print("演绎型用户风格：")
    print(f"  推理: {fp_ded.reasoning_style}, 类比: {fp_ded.analogy_preference}, 输出: {fp_ded.output_style}")
    print(f"  操作符: {ops_ded}")
    
    print("\n归纳型用户风格：")
    print(f"  推理: {fp_ind.reasoning_style}, 类比: {fp_ind.analogy_preference}, 输出: {fp_ind.output_style}")
    print(f"  操作符: {ops_ind}")
    
    # 简单验证
    passed = True
    if fp_ded.reasoning_style != "deductive":
        print("❌ 演绎型用户推理风格预期 'deductive'")
        passed = False
    if fp_ind.reasoning_style != "inductive":
        print("❌ 归纳型用户推理风格预期 'inductive'")
        passed = False
    if fp_ded.output_style != "conclusion_first":
        print("❌ 数据驱动用户输出风格预期 'conclusion_first'")
        passed = False
    if fp_ind.output_style != "evidence_first":
        print("❌ 叙事型用户输出风格预期 'evidence_first'")
        passed = False
    
    if passed:
        print("\n✅ 风格分析正确，不同用户获得不同操作符")
    else:
        print("\n❌ 风格分析未通过")
    
    return passed

if __name__ == "__main__":
    success = test_style_analysis()
    sys.exit(0 if success else 1)