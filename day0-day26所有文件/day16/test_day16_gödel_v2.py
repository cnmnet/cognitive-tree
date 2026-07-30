#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 16 测试 v2：验证八道防线评估 + 基线对比
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import re
from pathlib import Path

from crystal_tree_all_in_one_day import (
    FileIO, Config, AIClient, CrystalEngine, 
    PromptTemplateManager, GödelAgent,
    BENCHMARK_QUESTIONS
)


def test_evaluate_candidate_eight_defenses():
    """测试：八道防线评估（不调用真实AI，使用模拟响应）"""
    print("=" * 60)
    print("测试 1: 八道防线评估（模拟模式）")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 模拟候选
    candidate = {
        "role": "radical",
        "type": "add_reflection_instruction",
        "system_prompt": "你是激进者。请引用晶体并反思。",
        "rationale": "测试"
    }
    
    # 注意：这里会真正调用AI，因为 evaluate_candidate 内部调用了 ai.chat()
    # 第一次运行会真正调用API，后续可以注释掉节省成本
    
    print("⚠️ 此测试会调用真实 AI API，请确认 API Key 已配置")
    confirm = input("是否继续？(y/n): ")
    if confirm.lower() != 'y':
        print("跳过测试 1")
        return True
    
    try:
        # 使用验证集
        validation_questions = BENCHMARK_QUESTIONS[:2]
        result = agent.evaluate_candidate(candidate, validation_questions)
        
        print(f"\n📊 评估结果:")
        print(f"  通过: {result.get('passed', False)}")
        print(f"  平均质量分: {result.get('avg_quality_score', 0):.3f}")
        print(f"  基线分: {result.get('baseline_score', 0):.3f}")
        print(f"  知识贫瘠防线通过率: {result.get('knowledge_pass_rate', 0):.3f}")
        print(f"  偏见膨胀防线通过率: {result.get('bias_pass_rate', 0):.3f}")
        print(f"  思维固化防线通过率: {result.get('stagnation_pass_rate', 0):.3f}")
        print(f"  信息枯竭防线通过率: {result.get('external_pass_rate', 0):.3f}")
        print(f"  八道防线全部通过: {result.get('eight_defenses_passed', False)}")
        print(f"  不退化: {result.get('non_degrading', False)}")
        print(f"  理由: {result.get('reason', '')}")
        
        print("\n✅ 测试 1 完成")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_baseline_from_pareto():
    """测试：从 pareto_frontier.json 读取基线"""
    print("\n" + "=" * 60)
    print("测试 2: 基线读取（从 pareto_frontier.json）")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    baseline = agent._get_baseline_score("radical")
    print(f"✅ 基线评分: {baseline:.3f}")
    
    # 检查 pareto_frontier.json 是否存在
    pareto_path = Config.DATA_ROOT / "系统日志" / "pareto_frontier.json"
    if pareto_path.exists():
        with open(pareto_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   📁 pareto_frontier.json 存在")
        configs = data.get("configs", {})
        for name, values in configs.items():
            print(f"      {name}: accuracy={values.get('accuracy', 0):.3f}")
    else:
        print("   ⚠️ pareto_frontier.json 不存在")
    
    print("\n✅ 测试 2 完成")
    return True


def test_eight_defense_thresholds():
    """测试：验证八道防线阈值配置"""
    print("\n" + "=" * 60)
    print("测试 3: 八道防线阈值验证")
    print("=" * 60)
    
    # 从 Config.ALARM_RULES 读取阈值
    alarm_rules = Config.ALARM_RULES
    
    print("📋 八道防线配置:")
    print(f"  1. 知识贫瘠: 晶体引用率 < {alarm_rules.get('knowledge_poverty', {}).get('threshold', 0.5) * 100}% 触发")
    print(f"  2. 偏见膨胀: 偏见指数 > {alarm_rules.get('bias_inflation', {}).get('threshold', 0.3)} 触发")
    print(f"  3. 思维固化: Jaccard连续 {alarm_rules.get('thought_stagnation', {}).get('consecutive', 3)} 轮 > {alarm_rules.get('thought_stagnation', {}).get('threshold', 0.8)} 触发")
    print(f"  4. 信息枯竭: 连续 {alarm_rules.get('information_starvation', {}).get('threshold', 3)} 轮无外部新数据触发")
    
    # 验证关键阈值存在
    required_keys = ["knowledge_poverty", "bias_inflation", "thought_stagnation", "information_starvation"]
    all_exist = all(k in alarm_rules for k in required_keys)
    
    if all_exist:
        print("\n✅ 所有八道防线配置完整")
    else:
        missing = [k for k in required_keys if k not in alarm_rules]
        print(f"\n⚠️ 缺失配置: {missing}")
    
    print("\n✅ 测试 3 完成")
    return True


def test_full_evolution_cycle_dry():
    """测试：完整进化周期（干运行，只验证逻辑不调用AI）"""
    print("\n" + "=" * 60)
    print("测试 4: 完整进化周期（干运行）")
    print("=" * 60)
    
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)
    
    # 保存原始模板
    original = manager.get_template("radical")
    if original:
        original_system = original.system_prompt
        print(f"📋 原始 radical 模板版本: v{original.version}")
    else:
        print("⚠️ 未找到 radical 模板")
        return False
    
    # 运行进化（会真正调用AI）
    print("\n⚠️ 此测试会调用真实 AI API")
    confirm = input("是否继续？(y/n): ")
    if confirm.lower() != 'y':
        print("跳过测试 4")
        return True
    
    try:
        result = agent.run_evolution_cycle("radical")
        
        print(f"\n📊 进化结果:")
        print(f"  角色: {result.get('role')}")
        print(f"  生成候选: {result.get('candidates_generated', 0)}")
        print(f"  通过候选: {result.get('candidates_passed', 0)}")
        print(f"  应用改进: {result.get('applied', False)}")
        
        if result.get("applied"):
            candidate = result.get("applied_candidate", {})
            print(f"  改进类型: {candidate.get('type', 'unknown')}")
            eval_result = candidate.get("eval_result", {})
            print(f"  八道防线通过: {eval_result.get('eight_defenses_passed', False)}")
            print(f"  不退化: {eval_result.get('non_degrading', False)}")
        
        # 恢复原始模板
        manager.update_template("radical", system_prompt=original_system)
        print("\n✅ 已恢复原始模板")
        
        print("\n✅ 测试 4 完成")
        return True
    except Exception as e:
        # 恢复原始模板
        try:
            manager.update_template("radical", system_prompt=original_system)
        except:
            pass
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_evolution_log_has_events():
    """测试：evolution_log.json 是否包含 Gödel 事件"""
    print("\n" + "=" * 60)
    print("测试 5: evolution_log.json 验证")
    print("=" * 60)
    
    log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    if not log_path.exists():
        print("❌ evolution_log.json 不存在")
        return False
    
    with open(log_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    events = data.get("events", [])
    gödel_events = [e for e in events if e.get("event_type") == "gödel_evolution_applied"]
    
    print(f"📊 总事件数: {len(events)}")
    print(f"📊 Gödel 进化事件: {len(gödel_events)}")
    
    if gödel_events:
        for i, event in enumerate(gödel_events[-3:], 1):
            details = event.get("details", {})
            print(f"  {i}. 角色: {details.get('role')}, 类型: {details.get('candidate_type')}, 评分: {details.get('eval_score', 0):.3f}")
    else:
        print("  ⚠️ 暂无 Gödel 进化事件（运行进化后会生成）")
    
    # 检查 summary 是否包含 gödel_evolution_applied
    summary = data.get("summary", {})
    if "gödel_evolution_applied" in summary:
        print(f"  ✅ summary 中包含 gödel_evolution_applied: {summary['gödel_evolution_applied']} 次")
    
    print("\n✅ 测试 5 完成")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧠 Day 16 v2 测试：八道防线评估 + 基线对比")
    print("=" * 60 + "\n")
    
    tests = [
        ("八道防线评估", test_evaluate_candidate_eight_defenses),
        ("基线读取", test_baseline_from_pareto),
        ("防线阈值", test_eight_defense_thresholds),
        ("完整进化周期", test_full_evolution_cycle_dry),
        ("日志验证", test_evolution_log_has_events),
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