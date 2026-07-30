#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速强制探索 - 只测试2个孔洞
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crystal_tree_all_in_one_day import Config, FileIO, CrystalEngine, AIClient, ForceExplorer


def main():
    print("=" * 60)
    print("🚀 快速强制探索 - 只测试2个孔洞")
    print("=" * 60)

    # 初始化
    engine = CrystalEngine(FileIO(), ai_client=AIClient())
    explorer = ForceExplorer(engine, ai_client=AIClient())

    # 1. 获取需要探索的孔洞
    print("\n📋 检查需要强制探索的孔洞...")
    escalated = explorer.check_holes_for_escalation(threshold_days=1)
    print(f"   发现 {len(escalated)} 个需要探索的孔洞")

    if not escalated:
        print("   ✅ 没有需要探索的孔洞")
        return

    # 2. 只取前2个
    test_holes = escalated[:2]
    print(f"\n📋 选择前2个孔洞进行测试:")
    for i, h in enumerate(test_holes, 1):
        print(f"   {i}. {h['hole_id']} (紧迫度: {h['urgency']})")

    # 3. 探索
    print("\n" + "=" * 60)
    print("🚀 开始强制探索...")
    print("=" * 60)

    for i, h in enumerate(test_holes, 1):
        print(f"\n[{i}/2] 探索孔洞: {h['hole_id']}")
        try:
            result = explorer.force_explore(h['hole_id'], force_level="high")
            if result.get("crystal_generated"):
                print(f"   ✅ 生成晶体: {result['crystal_generated']}")
            else:
                print(f"   ⚠️ 失败: {result.get('error', '未知错误')}")
        except Exception as e:
            print(f"   ❌ 异常: {e}")

    # 4. 查看最终状态
    print("\n" + "=" * 60)
    print("📊 最终状态")
    print("=" * 60)

    status = explorer.get_exploration_status()
    print(f"   探索记录数: {status.get('exploration_log_count', 0)}")
    print(f"   待升级孔洞: {status.get('pending_escalation', 0)}")

    # 5. 查看 skills/ 目录
    skills_dir = Config.DATA_ROOT / "skills"
    if skills_dir.exists():
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("C")]
        print(f"\n   skills/ 目录: {len(skill_dirs)} 个 Skill")

        # 显示最新的3个
        latest = sorted(skill_dirs, key=lambda x: x.stat().st_ctime, reverse=True)[:3]
        if latest:
            print("   最新创建的 Skill:")
            for d in latest:
                print(f"      - {d.name}")

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()