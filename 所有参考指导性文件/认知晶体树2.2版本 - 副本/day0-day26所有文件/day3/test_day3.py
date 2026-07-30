#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 3 测试：元原语协作网络升级
"""

import sys
import os
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import Config, FileIO, CrystalEngine, MetaLayer

def test_chain_trigger():
    """测试触发链是否正常工作"""
    print("🧪 Day 3 测试：元原语触发链")
    
    # 初始化
    FileIO.ensure_directories()
    files = FileIO()
    engine = CrystalEngine(files)
    meta = MetaLayer(engine, files)
    
    # 模拟数据：创建一些孤立晶体
    # 先清空晶体文件，添加一些孤立晶体
    files.write("crystals", """# 晶体卡片库

| ID | 内容 | 链接 |
|----|------|------|
| C001 | 孤立晶体1：测试主动缺口检测 | — |
| C002 | 孤立晶体2：另一个测试晶体 | — |
| C003 | 孤立晶体3：第三个孤立晶体 | — |
| C004 | 晶体4：与其他晶体有链接 | C005 |
| C005 | 晶体5：与其他晶体有链接 | C004 |
""")
    
    # 运行所有元原语（含触发链）
    print("📊 运行所有元原语...")
    results = meta.run_all_primitives()
    
    # 检查触发链结果
    triggered = results.get("triggered_chains", [])
    print(f"\n触发链执行结果：{len(triggered)} 条触发链")
    
    for chain in triggered:
        print(f"  ✅ {chain['chain']}: {chain['source']} → {chain['target']}")
        print(f"     来源结果: {chain.get('source_result', '')}")
        print(f"     目标结果: {chain.get('target_result', '')}")
        print(f"     通过: {'✅' if chain.get('passed') else '❌'}")
    
    # 检查 change_log 是否有触发链记录
    change_log = files.read("change_log")
    if "元原语触发链" in change_log:
        print("\n✅ change_log 中包含触发链记录")
    else:
        print("\n❌ change_log 中未找到触发链记录")
    
    # 检查 evolution_log.json
    evo_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    if evo_path.exists():
        with open(evo_path, "r", encoding="utf-8") as f:
            evo_data = json.load(f)
        chain_events = [e for e in evo_data.get("events", []) if e.get("event_type") == "chain_triggered"]
        print(f"✅ evolution_log.json 中有 {len(chain_events)} 条链触发事件")
    
    # 验收结果
    passed = len(triggered) >= 1 and "元原语触发链" in change_log
    print(f"\n验收结果：{'✅ 通过' if passed else '❌ 失败'}")
    return passed

if __name__ == "__main__":
    success = test_chain_trigger()
    sys.exit(0 if success else 1)