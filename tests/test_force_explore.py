#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动测试强制探索 - 重置孔洞状态并强制探索
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crystal_tree_all_in_one_day import Config, FileIO, CrystalEngine, AIClient, ForceExplorer

def main():
    print("=" * 60)
    print("🧪 手动测试强制探索")
    print("=" * 60)

    # 初始化
    engine = CrystalEngine(FileIO(), ai_client=AIClient())
    explorer = ForceExplorer(engine, ai_client=AIClient())

    # 1. 查看当前孔洞
    holes = engine.parse_holes()
    print(f"\n📋 当前孔洞数: {len(holes)}")
    high_priority = [h for h in holes if h.urgency >= 0.7]
    print(f"   高优先级孔洞: {len(high_priority)}")

    for h in high_priority[:5]:
        print(f"   - {h.id}: 紧迫度={h.urgency}, 内容={h.content[:40]}...")

    # 2. 重置探索状态（删除旧的探索记录，让孔洞重新变为"待探索"状态）
    state_file = Config.DATA_ROOT / "系统日志" / "exploration_state.json"
    if state_file.exists():
        print(f"\n📄 重置探索状态文件: {state_file}")
        # 备份原文件
        backup_file = state_file.with_suffix(".json.bak")
        state_file.rename(backup_file)
        print(f"   已备份到: {backup_file}")

    # 3. 重新加载 explorer（会创建新的空状态）
    explorer = ForceExplorer(engine, ai_client=AIClient())

    # 4. 检查需要探索的孔洞
    print("\n🔍 检查需要强制探索的孔洞...")
    escalated = explorer.check_holes_for_escalation(threshold_days=1)
    print(f"   发现 {len(escalated)} 个需要探索的孔洞")

    if not escalated:
        print("   ⚠️ 没有需要探索的孔洞，尝试使用 force_level='high' 强制探索一个孔洞")
        # 强制探索第一个高优先级孔洞
        if high_priority:
            test_hole = high_priority[0]
            print(f"\n🚀 强制探索: {test_hole.id}")
            result = explorer.force_explore(test_hole.id, force_level="high")
            print(f"   结果: {result}")
            if result.get("crystal_generated"):
                print(f"   ✅ 生成晶体: {result['crystal_generated']}")
            else:
                print(f"   ⚠️ 未生成晶体: {result.get('error', '未知错误')}")
    else:
        # 探索前3个孔洞
        for h in escalated[:3]:
            print(f"\n🚀 强制探索: {h['hole_id']} (紧迫度: {h['urgency']})")
            result = explorer.force_explore(h['hole_id'], force_level="high")
            if result.get("crystal_generated"):
                print(f"   ✅ 生成晶体: {result['crystal_generated']}")
            else:
                print(f"   ⚠️ 未生成晶体: {result.get('error', '未知错误')}")

    # 5. 检查 skills/ 目录变化
    skills_dir = Config.DATA_ROOT / "skills"
    if skills_dir.exists():
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("C")]
        print(f"\n📁 skills/ 目录: {len(skill_dirs)} 个 Skill")
        # 显示最新的5个
        latest = sorted(skill_dirs, key=lambda x: x.stat().st_ctime, reverse=True)[:5]
        for d in latest:
            print(f"   - {d.name}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()