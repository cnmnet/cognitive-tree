#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 1 验收测试：人为制造低引用率场景，验证知识贫瘠警报
"""

import sys
import os
import json
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import (
    Config, FileIO, CrystalEngine, DebateEngine, AIClient
)

def test_day1():
    print("🧪 Day 1 验收测试：知识贫瘠警报")

    # 初始化
    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())
    ai = AIClient(api_key=Config.get_api_key())
    if not ai.api_key:
        print("❌ 请配置 DEEPSEEK_API_KEY")
        return False

    roles = [
        {"key": "radical", "name": "激进者", "instruction": "攻击默认前提"},
        {"key": "conservative", "name": "保守者", "instruction": "风险优先"},
        {"key": "structural", "name": "结构主义者", "instruction": "寻找同构案例"},
    ]

    # 修改引擎，使 rank_crystals 返回空列表（模拟无晶体）
    original_rank = engine.rank_crystals
    def empty_rank(*args, **kwargs):
        return []   # 返回空，导致引用率为0
    engine.rank_crystals = empty_rank

    # 创建DebateEngine，使用自定义log以捕获警报信息
    alarm_log = []

    def log_callback(msg, level="system"):
        print(f"[{level}] {msg}")
        if "知识贫瘠警报" in msg:
            alarm_log.append(msg)

    debate = DebateEngine(
        ai, engine, roles,
        log=log_callback,
        progress_callback=None
    )

    # 运行一个简单问题
    question = "如何提升团队效率？"
    print(f"\n运行辩论，问题：{question}")
    result = debate.run(question, mode="debate_full", max_rounds=2)

    # 检查警报日志
    if any("知识贫瘠警报" in msg for msg in alarm_log):
        print("\n✅ 知识贫瘠警报已触发！")
        # 检查 evolution_log.json 中是否有记录
        evo_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        if evo_path.exists():
            with open(evo_path, "r", encoding="utf-8") as f:
                evo_data = json.load(f)
            alarm_events = [e for e in evo_data.get("events", []) if e.get("event_type") == "alarm"]
            if alarm_events:
                print(f"✅ evolution_log.json 中找到 {len(alarm_events)} 条警报记录")
                for ev in alarm_events:
                    if ev["details"].get("rule") == "knowledge_poverty":
                        print(f"   - {ev['details']['message']}")
                        return True
            else:
                print("❌ evolution_log.json 中未找到警报记录")
                return False
        else:
            print("❌ evolution_log.json 不存在")
            return False
    else:
        print("❌ 知识贫瘠警报未触发")
        return False

if __name__ == "__main__":
    success = test_day1()
    sys.exit(0 if success else 1)