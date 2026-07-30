#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 1 全面警报测试：验证四种警报均能正确触发并记录到 evolution_log.json
"""

import sys
import os
import json
import re
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import (
    Config, FileIO, CrystalEngine, DebateEngine, AIClient, AlarmMonitor
)

# 测试日志
test_results = []

def log_result(name, passed, msg=""):
    status = "✅" if passed else "❌"
    test_results.append((name, passed))
    print(f"{status} {name}: {msg}")

def clear_evolution_log():
    """清空 evolution_log.json 以便每次测试独立"""
    log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    if log_path.exists():
        os.remove(log_path)

def read_evolution_log():
    """读取 evolution_log.json 内容"""
    log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    if not log_path.exists():
        return {"events": []}
    with open(log_path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_knowledge_poverty():
    """测试知识贫瘠警报（晶体引用率 < 0.5）"""
    print("\n🧪 测试 1: 知识贫瘠警报")
    clear_evolution_log()

    # 初始化
    FileIO.ensure_directories()
    engine = CrystalEngine(FileIO())
    ai = AIClient(api_key=Config.get_api_key())
    if not ai.api_key:
        log_result("知识贫瘠警报", False, "未配置 API Key")
        return

    # Monkey Patch: 让 get_associative_crystals 返回空列表，导致引用率为0
    original_get = engine.get_associative_crystals
    def empty_get(*args, **kwargs):
        return []
    engine.get_associative_crystals = empty_get

    roles = [
        {"key": "radical", "name": "激进者", "instruction": "攻击默认前提"},
        {"key": "conservative", "name": "保守者", "instruction": "风险优先"},
        {"key": "structural", "name": "结构主义者", "instruction": "寻找同构案例"},
    ]

    debate = DebateEngine(ai, engine, roles, log=lambda m, l: None)
    # 为了快速，只跑2轮
    result = debate.run("如何提升团队效率？", mode="debate_full", max_rounds=2)

    # 恢复原方法
    engine.get_associative_crystals = original_get

    # 检查 evolution_log.json 中是否有 knowledge_poverty 记录
    log_data = read_evolution_log()
    events = log_data.get("events", [])
    alarm_events = [e for e in events if e.get("event_type") == "alarm" and e.get("details", {}).get("rule") == "knowledge_poverty"]
    if alarm_events:
        log_result("知识贫瘠警报", True, f"触发 {len(alarm_events)} 次")
    else:
        log_result("知识贫瘠警报", False, "未在 evolution_log.json 中找到对应记录")

def test_bias_inflation():
    """测试偏见膨胀警报（偏见强化指数 > 0.3）"""
    print("\n🧪 测试 2: 偏见膨胀警报")
    clear_evolution_log()

    # 直接测试 AlarmMonitor 的 check 方法，因为偏见指标难以在辩论中自然产生
    monitor = AlarmMonitor()
    metrics = {
        "crystal_reference_rate": 1.0,   # 满足其他
        "bias_amplification": 0.5,       # > 0.3
        "external_has_new": True,
        "jaccard_similarity": 0.1
    }
    triggered = monitor.check(metrics)

    # 手动记录到 evolution_log（模拟实际流程）
    engine = CrystalEngine(FileIO())
    for alarm in triggered:
        engine.log_evolution_event(
            "alarm",
            {
                "rule": alarm["rule"],
                "message": alarm["message"],
                "action": alarm["action"],
                "data": alarm.get("data", {}),
                "round": 1,
                "trigger": "alarm"
            }
        )

    log_data = read_evolution_log()
    events = log_data.get("events", [])
    alarm_events = [e for e in events if e.get("event_type") == "alarm" and e.get("details", {}).get("rule") == "bias_inflation"]
    if alarm_events:
        log_result("偏见膨胀警报", True, f"触发 {len(alarm_events)} 次")
    else:
        log_result("偏见膨胀警报", False, "未在 evolution_log.json 中找到对应记录")

def test_information_starvation():
    """测试信息枯竭警报（连续3轮无新外部数据）"""
    print("\n🧪 测试 3: 信息枯竭警报")
    clear_evolution_log()

    # 模拟连续3轮无新外部数据
    monitor = AlarmMonitor()
    # 第一轮无新数据
    metrics1 = {
        "crystal_reference_rate": 1.0,
        "bias_amplification": 0.0,
        "external_has_new": False,   # 无新数据
        "jaccard_similarity": 0.1
    }
    monitor.check(metrics1)
    # 第二轮无新数据
    monitor.check(metrics1)
    # 第三轮无新数据，应触发
    triggered = monitor.check(metrics1)

    engine = CrystalEngine(FileIO())
    for alarm in triggered:
        engine.log_evolution_event(
            "alarm",
            {
                "rule": alarm["rule"],
                "message": alarm["message"],
                "action": alarm["action"],
                "data": alarm.get("data", {}),
                "round": 3,
                "trigger": "alarm"
            }
        )

    log_data = read_evolution_log()
    events = log_data.get("events", [])
    alarm_events = [e for e in events if e.get("event_type") == "alarm" and e.get("details", {}).get("rule") == "information_starvation"]
    if alarm_events:
        log_result("信息枯竭警报", True, f"触发 {len(alarm_events)} 次")
    else:
        log_result("信息枯竭警报", False, "未在 evolution_log.json 中找到对应记录")

def test_thought_stagnation():
    """测试思维固化警报（Jaccard连续3轮 > 0.8）"""
    print("\n🧪 测试 4: 思维固化警报")
    clear_evolution_log()

    # 模拟连续3轮高Jaccard
    monitor = AlarmMonitor()
    metrics = {
        "crystal_reference_rate": 1.0,
        "bias_amplification": 0.0,
        "external_has_new": True,
        "jaccard_similarity": 0.85   # > 0.8
    }
    # 连续3轮
    monitor.check(metrics)
    monitor.check(metrics)
    triggered = monitor.check(metrics)

    engine = CrystalEngine(FileIO())
    for alarm in triggered:
        engine.log_evolution_event(
            "alarm",
            {
                "rule": alarm["rule"],
                "message": alarm["message"],
                "action": alarm["action"],
                "data": alarm.get("data", {}),
                "round": 3,
                "trigger": "alarm"
            }
        )

    log_data = read_evolution_log()
    events = log_data.get("events", [])
    alarm_events = [e for e in events if e.get("event_type") == "alarm" and e.get("details", {}).get("rule") == "thought_stagnation"]
    if alarm_events:
        log_result("思维固化警报", True, f"触发 {len(alarm_events)} 次")
    else:
        log_result("思维固化警报", False, "未在 evolution_log.json 中找到对应记录")

def main():
    print("=" * 60)
    print("Day 1 四种警报全面测试")
    print("=" * 60)

    # 确保 Config.ALARM_RULES 已正确定义
    if not hasattr(Config, "ALARM_RULES"):
        print("❌ Config.ALARM_RULES 未定义，请先添加警报规则配置。")
        sys.exit(1)

    # 运行所有测试
    test_knowledge_poverty()
    test_bias_inflation()
    test_information_starvation()
    test_thought_stagnation()

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    all_passed = True
    for name, passed in test_results:
        print(f"  {'✅' if passed else '❌'} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 所有警报测试通过！Day 1 验收完成。")
    else:
        print("\n⚠️ 部分测试未通过，请检查相关代码。")
        sys.exit(1)

if __name__ == "__main__":
    main()