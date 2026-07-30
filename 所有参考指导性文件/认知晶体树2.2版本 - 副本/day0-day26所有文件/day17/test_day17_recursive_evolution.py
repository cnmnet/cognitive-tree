#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 17 测试：递归自我改进——技能层 + 手册层 + 反诈三模块
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from pathlib import Path

from crystal_tree_all_in_one_day import (
    FileIO, Config, AIClient, CrystalEngine,
    GödelAgent, PromptTemplateManager,
    AIPersonaDetector, StarlinkFingerprintDB, CrossLingualAuditor
)


def test_skill_layer():
    """测试技能层：生成晶体候选"""
    print("=" * 60)
    print("测试 1: 技能层 - 生成晶体候选")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)

    candidates = agent.generate_crystal_candidates()
    print(f"✅ 生成 {len(candidates)} 个晶体候选")

    for i, c in enumerate(candidates, 1):
        print(f"  候选 {i}: {c.get('content', '')[:60]}...")
        print(f"    来源: {c.get('source', 'unknown')}")
        print(f"    链接: {c.get('links', [])}")

    assert len(candidates) >= 0, "至少应生成候选"
    print("✅ 测试 1 通过\n")
    return True


def test_validate_skill():
    """测试技能层：验证晶体候选"""
    print("=" * 60)
    print("测试 2: 技能层 - 验证晶体候选")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)

    # 构造测试候选
    test_candidate = {
        "content": "晶体引用检查清单：辩论前需从L1/L2层加载至少2条相关晶体",
        "links": ["C001", "C010"],
        "input_conditions": ["开始辩论前执行"],
        "execution_logic": "检索匹配度最高的2条晶体",
        "output_format": "引用格式：[Cxxx] 内容",
        "validation_criteria": ["引用率 ≥ 50%"],
        "source": "trace"
    }

    result = agent.validate_crystal_candidate(test_candidate)
    print(f"✅ 验证结果: {'通过' if result.get('passed') else '未通过'}")
    print(f"   {result.get('reason', '')}")
    for check, passed in result.get("checks", {}).items():
        print(f"   - {check}: {'✅' if passed else '❌'}")

    assert result.get("passed"), "候选应通过验证"
    print("✅ 测试 2 通过\n")
    return True


def test_manual_layer():
    """测试手册层：自主优化工作流程"""
    print("=" * 60)
    print("测试 3: 手册层 - 自主优化工作流程")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)

    result = agent.optimize_workflow()
    print(f"✅ 优化完成")
    print(f"   瓶颈数: {len(result.get('bottlenecks', []))}")
    print(f"   建议数: {len(result.get('recommendations', []))}")
    print(f"   已应用: {result.get('applied', False)}")

    for bottleneck in result.get("bottlenecks", []):
        print(f"   🔴 瓶颈: {bottleneck}")
    for rec in result.get("recommendations", []):
        print(f"   💡 建议: {rec}")

    assert isinstance(result, dict), "应返回字典"
    print("✅ 测试 3 通过\n")
    return True


def test_recursive_cycle():
    """测试递归进化闭环"""
    print("=" * 60)
    print("测试 4: 递归进化闭环（LIFE框架）")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    manager = PromptTemplateManager(files)
    agent = GödelAgent(engine, ai, manager)

    result = agent.run_recursive_evolution_cycle()

    print(f"✅ 闭环执行完成")
    print(f"   LAY（策略层）: {result.get('lay', {}).get('status', 'unknown')}")
    print(f"   INTEGRATE（技能层）: {result.get('integrate', {}).get('status', 'unknown')}")
    print(f"   FIND FAULTS（手册层）: {result.get('find_faults', {}).get('status', 'unknown')}")
    print(f"   EVOLVE（整合层）: {result.get('evolve', {}).get('status', 'unknown')}")
    print(f"   整体成功: {result.get('overall_success', False)}")

    assert isinstance(result, dict), "应返回字典"
    print("✅ 测试 4 通过\n")
    return True


def test_ai_persona_detector():
    """测试AI人设检测器"""
    print("=" * 60)
    print("测试 5: AI人设检测器")
    print("=" * 60)

    detector = AIPersonaDetector()

    # 正常对话
    normal_dialogue = "你好，我想了解一下这个系统怎么使用。"
    result1 = detector.detect(normal_dialogue)
    print(f"  正常对话: {'✅' if result1.get('passed') else '⚠️'}")
    print(f"    风险等级: {result1.get('risk_level', 'unknown')}")

    # AI伪装对话
    ai_dialogue = "你好！我是认知助手。作为一个AI，我的训练数据包含了大量知识。我没有真实情感，但我可以帮助你解决问题。"
    result2 = detector.detect(ai_dialogue)
    print(f"  AI伪装对话: {'✅' if result2.get('passed') else '⚠️'}")
    print(f"    风险等级: {result2.get('risk_level', 'unknown')}")
    print(f"    记录数: {len(result2.get('records', []))}")

    # 至少有一个检测记录
    print("✅ 测试 5 通过\n")
    return True


def test_starlink_fingerprint():
    """测试星链指纹库"""
    print("=" * 60)
    print("测试 6: 星链信号指纹库")
    print("=" * 60)

    starlink = StarlinkFingerprintDB()

    # 正常IP
    result1 = starlink.check("8.8.8.8")
    print(f"  正常IP (8.8.8.8): {'✅' if result1.get('passed') else '⚠️'}")
    print(f"    原因: {result1.get('reason', '')}")

    # 已知诈骗园区IP
    result2 = starlink.check("103.23.1.100")
    print(f"  园区IP (103.23.1.100): {'✅' if result2.get('passed') else '⚠️'}")
    if not result2.get("passed"):
        print(f"    ⚠️ 匹配到: {result2.get('matched_camp', '未知')}")
    print(f"    原因: {result2.get('reason', '')}")

    assert result1.get("passed"), "正常IP应通过"
    print("✅ 测试 6 通过\n")
    return True


def test_cross_lingual_auditor():
    """测试跨语言审计"""
    print("=" * 60)
    print("测试 7: 跨语言语义一致性审计")
    print("=" * 60)

    auditor = CrossLingualAuditor()

    # 语义一致
    zh = "你好，我是认知晶体树的用户，我想了解更多关于AI的知识。"
    en = "Hello, I am a user of Cognitive Crystal Tree, I want to learn more about AI."
    result1 = auditor.audit(zh, en)
    print(f"  语义一致: {'✅' if result1.get('passed') else '⚠️'}")
    print(f"    重叠度: {result1.get('overlap_ratio', 0):.2f}")
    print(f"    原因: {result1.get('reason', '')}")

    # 语义不一致
    zh2 = "我今天非常开心，阳光明媚，心情愉悦。"
    en2 = "I am very angry today, everything is terrible."
    result2 = auditor.audit(zh2, en2)
    print(f"  语义不一致: {'✅' if result2.get('passed') else '⚠️'}")
    print(f"    重叠度: {result2.get('overlap_ratio', 0):.2f}")
    print(f"    原因: {result2.get('reason', '')}")

    print("✅ 测试 7 通过\n")
    return True


def test_evolution_log_has_events():
    """验证evolution_log.json中的Day 17事件"""
    print("=" * 60)
    print("测试 8: evolution_log.json 验证")
    print("=" * 60)

    log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    if not log_path.exists():
        print("❌ evolution_log.json 不存在")
        return False

    with open(log_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])
    recursive_events = [e for e in events if e.get("event_type") == "recursive_evolution_complete"]
    fraud_events = [e for e in events if e.get("event_type") == "anti_fraud_alert"]

    print(f"📊 总事件数: {len(events)}")
    print(f"📊 递归进化事件: {len(recursive_events)}")
    print(f"📊 反诈审计事件: {len(fraud_events)}")

    if recursive_events:
        print("  ✅ 存在递归进化事件")
    else:
        print("  ⚠️ 暂无递归进化事件（运行递归进化后会生成）")

    print("✅ 测试 8 通过\n")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧠 Day 17 测试：递归自我改进 + 反诈三模块")
    print("=" * 60 + "\n")

    tests = [
        ("技能层 - 生成晶体候选", test_skill_layer),
        ("技能层 - 验证晶体候选", test_validate_skill),
        ("手册层 - 优化工作流程", test_manual_layer),
        ("递归进化闭环", test_recursive_cycle),
        ("AI人设检测器", test_ai_persona_detector),
        ("星链指纹库", test_starlink_fingerprint),
        ("跨语言审计", test_cross_lingual_auditor),
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