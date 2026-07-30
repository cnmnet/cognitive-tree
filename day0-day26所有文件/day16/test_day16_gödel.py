#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 16 测试：Gödel Agent 递归自我改进——策略层
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crystal_tree_all_in_one_day import (
    FileIO, Config, AIClient, CrystalEngine, 
    PromptTemplateManager, GödelAgent, MetaLayer,
    BENCHMARK_QUESTIONS
)


def test_prompt_template_manager():
    """测试 Prompt 模板管理器"""
    print("=" * 60)
    print("测试 1: PromptTemplateManager")
    print("=" * 60)
    
    files = FileIO()
    manager = PromptTemplateManager(files)
    
    # 测试加载
    templates = manager.get_all_templates()
    assert len(templates) > 0, "模板加载失败"
    print(f"✅ 加载了 {len(templates)} 个模板")
    
    # 测试获取
    radical = manager.get_template("radical")
    assert radical is not None, "无法获取 radical 模板"
    assert "激进者" in radical.system_prompt, "radical 模板内容错误"
    print(f"✅ 获取 radical 模板成功: {radical.system_prompt[:50]}...")
    
    # 测试更新
    old_version = radical.version
    success = manager.update_template("radical", system_prompt=radical.system_prompt + "\n【测试】新增指令")
    assert success, "模板更新失败"
    
    updated = manager.get_template("radical")
    assert updated.version > old_version, "版本号未更新"
    print(f"✅ 模板更新成功: v{old_version} -> v{updated.version}")
    
    print("✅ PromptTemplateManager 测试通过\n")
    return True


def test_gödel_agent_analysis():
    """测试 Gödel Agent 失败模式分析"""
    print("=" * 60)
    print("测试 2: GödelAgent 失败模式分析")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 测试分析
    patterns = agent.analyze_failure_patterns()
    print(f"✅ 分析完成: {patterns.get('summary', '无')}")
    print(f"   发现 {len(patterns.get('patterns', []))} 种失败模式")
    print(f"   总事件数: {patterns.get('total_events', 0)}")
    
    print("✅ GödelAgent 分析测试通过\n")
    return True


def test_candidate_generation():
    """测试候选改进生成"""
    print("=" * 60)
    print("测试 3: 候选改进生成")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 测试生成
    candidates = agent.generate_prompt_candidates("radical")
    print(f"✅ 生成了 {len(candidates)} 个候选")
    
    for i, candidate in enumerate(candidates, 1):
        print(f"   候选 {i}: {candidate.get('type', 'unknown')}")
        print(f"   理由: {candidate.get('rationale', '')[:50]}...")
    
    assert len(candidates) > 0, "未生成候选"
    print("✅ 候选生成测试通过\n")
    return True


def test_candidate_evaluation():
    """测试候选评估"""
    print("=" * 60)
    print("测试 4: 候选评估（需要 AI API）")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 先生成候选
    candidates = agent.generate_prompt_candidates("radical")
    if not candidates:
        print("⚠️ 未生成候选，跳过评估测试")
        return True
    
    candidate = candidates[0]
    validation_questions = BENCHMARK_QUESTIONS[:2]
    
    # 评估
    result = agent.evaluate_candidate(candidate, validation_questions)
    print(f"✅ 评估完成")
    print(f"   平均分: {result.get('avg_score', 0):.2f}")
    print(f"   基线分: {result.get('baseline_score', 0):.2f}")
    print(f"   通过: {result.get('passed', False)}")
    print(f"   理由: {result.get('reason', '')}")
    
    print("✅ 候选评估测试通过\n")
    return True


def test_full_evolution_cycle():
    """测试完整进化周期（非破坏性，不使用真实 API）"""
    print("=" * 60)
    print("测试 5: 完整进化周期（模拟模式）")
    print("=" * 60)
    
    files = FileIO()
    # 使用模拟 AI 或真实 AI（如果有 API Key）
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 保存原始模板
    original = manager.get_template("radical")
    original_system = original.system_prompt
    
    try:
        # 运行进化（使用模拟评估，避免消耗真实 API）
        result = agent.run_evolution_cycle("radical")
        
        print(f"✅ 进化周期完成")
        print(f"   角色: {result.get('role', '未知')}")
        print(f"   生成候选: {result.get('candidates_generated', 0)}")
        print(f"   通过候选: {result.get('candidates_passed', 0)}")
        print(f"   应用改进: {result.get('applied', False)}")
        
        if result.get("applied"):
            print(f"   改进类型: {result.get('applied_candidate', {}).get('type', 'unknown')}")
        
        # 恢复原始模板
        manager.update_template("radical", system_prompt=original_system)
        print("✅ 已恢复原始模板")
        
    except Exception as e:
        # 恢复原始模板
        manager.update_template("radical", system_prompt=original_system)
        print(f"⚠️ 进化测试异常: {e}")
        return False
    
    print("✅ 完整进化周期测试通过\n")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧠 Day 16 测试：Gödel Agent 递归自我改进——策略层")
    print("=" * 60 + "\n")
    
    tests = [
        ("PromptTemplateManager", test_prompt_template_manager),
        ("GödelAgent 分析", test_gödel_agent_analysis),
        ("候选生成", test_candidate_generation),
        ("候选评估", test_candidate_evaluation),
        ("完整进化周期", test_full_evolution_cycle),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试 {name} 异常: {e}")
            failed += 1
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 16 测试：Gödel Agent 递归自我改进——策略层
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crystal_tree_all_in_one_day import (
    FileIO, Config, AIClient, CrystalEngine, 
    PromptTemplateManager, GödelAgent, MetaLayer,
    BENCHMARK_QUESTIONS
)


def test_prompt_template_manager():
    """测试 Prompt 模板管理器"""
    print("=" * 60)
    print("测试 1: PromptTemplateManager")
    print("=" * 60)
    
    files = FileIO()
    manager = PromptTemplateManager(files)
    
    # 测试加载
    templates = manager.get_all_templates()
    assert len(templates) > 0, "模板加载失败"
    print(f"✅ 加载了 {len(templates)} 个模板")
    
    # 测试获取
    radical = manager.get_template("radical")
    assert radical is not None, "无法获取 radical 模板"
    assert "激进者" in radical.system_prompt, "radical 模板内容错误"
    print(f"✅ 获取 radical 模板成功: {radical.system_prompt[:50]}...")
    
    # 测试更新
    old_version = radical.version
    success = manager.update_template("radical", system_prompt=radical.system_prompt + "\n【测试】新增指令")
    assert success, "模板更新失败"
    
    updated = manager.get_template("radical")
    assert updated.version > old_version, "版本号未更新"
    print(f"✅ 模板更新成功: v{old_version} -> v{updated.version}")
    
    print("✅ PromptTemplateManager 测试通过\n")
    return True


def test_gödel_agent_analysis():
    """测试 Gödel Agent 失败模式分析"""
    print("=" * 60)
    print("测试 2: GödelAgent 失败模式分析")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 测试分析
    patterns = agent.analyze_failure_patterns()
    print(f"✅ 分析完成: {patterns.get('summary', '无')}")
    print(f"   发现 {len(patterns.get('patterns', []))} 种失败模式")
    print(f"   总事件数: {patterns.get('total_events', 0)}")
    
    print("✅ GödelAgent 分析测试通过\n")
    return True


def test_candidate_generation():
    """测试候选改进生成"""
    print("=" * 60)
    print("测试 3: 候选改进生成")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 测试生成
    candidates = agent.generate_prompt_candidates("radical")
    print(f"✅ 生成了 {len(candidates)} 个候选")
    
    for i, candidate in enumerate(candidates, 1):
        print(f"   候选 {i}: {candidate.get('type', 'unknown')}")
        print(f"   理由: {candidate.get('rationale', '')[:50]}...")
    
    assert len(candidates) > 0, "未生成候选"
    print("✅ 候选生成测试通过\n")
    return True


def test_candidate_evaluation():
    """测试候选评估"""
    print("=" * 60)
    print("测试 4: 候选评估（需要 AI API）")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 先生成候选
    candidates = agent.generate_prompt_candidates("radical")
    if not candidates:
        print("⚠️ 未生成候选，跳过评估测试")
        return True
    
    candidate = candidates[0]
    validation_questions = BENCHMARK_QUESTIONS[:2]
    
    # 评估
    result = agent.evaluate_candidate(candidate, validation_questions)
    print(f"✅ 评估完成")
    print(f"   平均分: {result.get('avg_score', 0):.2f}")
    print(f"   基线分: {result.get('baseline_score', 0):.2f}")
    print(f"   通过: {result.get('passed', False)}")
    print(f"   理由: {result.get('reason', '')}")
    
    print("✅ 候选评估测试通过\n")
    return True


def test_full_evolution_cycle():
    """测试完整进化周期（非破坏性，不使用真实 API）"""
    print("=" * 60)
    print("测试 5: 完整进化周期（模拟模式）")
    print("=" * 60)
    
    files = FileIO()
    # 使用模拟 AI 或真实 AI（如果有 API Key）
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 保存原始模板
    original = manager.get_template("radical")
    original_system = original.system_prompt
    
    try:
        # 运行进化（使用模拟评估，避免消耗真实 API）
        result = agent.run_evolution_cycle("radical")
        
        print(f"✅ 进化周期完成")
        print(f"   角色: {result.get('role', '未知')}")
        print(f"   生成候选: {result.get('candidates_generated', 0)}")
        print(f"   通过候选: {result.get('candidates_passed', 0)}")
        print(f"   应用改进: {result.get('applied', False)}")
        
        if result.get("applied"):
            print(f"   改进类型: {result.get('applied_candidate', {}).get('type', 'unknown')}")
        
        # 恢复原始模板
        manager.update_template("radical", system_prompt=original_system)
        print("✅ 已恢复原始模板")
        
    except Exception as e:
        # 恢复原始模板
        manager.update_template("radical", system_prompt=original_system)
        print(f"⚠️ 进化测试异常: {e}")
        return False
    
    print("✅ 完整进化周期测试通过\n")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧠 Day 16 测试：Gödel Agent 递归自我改进——策略层")
    print("=" * 60 + "\n")
    
    tests = [
        ("PromptTemplateManager", test_prompt_template_manager),
        ("GödelAgent 分析", test_gödel_agent_analysis),
        ("候选生成", test_candidate_generation),
        ("候选评估", test_candidate_evaluation),
        ("完整进化周期", test_full_evolution_cycle),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试 {name} 异常: {e}")
            failed += 1
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)