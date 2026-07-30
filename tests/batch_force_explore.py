#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量强制探索 - 一次性处理所有待升级孔洞
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crystal_tree_all_in_one_day import Config, FileIO, CrystalEngine, AIClient, ForceExplorer


def main():
    print("=" * 60)
    print("🚀 批量强制探索 - 处理所有待升级孔洞")
    print("=" * 60)

    # 初始化
    engine = CrystalEngine(FileIO(), ai_client=AIClient())
    explorer = ForceExplorer(engine, ai_client=AIClient())

    # 1. 获取所有需要探索的孔洞
    print("\n📋 检查需要强制探索的孔洞...")
    escalated = explorer.check_holes_for_escalation(threshold_days=1)
    print(f"   发现 {len(escalated)} 个需要探索的孔洞")

    if not escalated:
        print("   ✅ 没有需要探索的孔洞，全部已完成！")
        return

    # 2. 显示孔洞列表
    print("\n📋 待探索孔洞列表:")
    for i, h in enumerate(escalated, 1):
        print(f"   {i}. {h['hole_id']} (紧迫度: {h['urgency']}) - {h['content'][:30]}...")

    # 3. 确认是否继续
    confirm = input(f"\n是否继续批量探索这 {len(escalated)} 个孔洞？(y/n): ")
    if confirm.lower() != 'y':
        print("已取消")
        return

    # 4. 批量探索
    print("\n" + "=" * 60)
    print("🚀 开始批量强制探索...")
    print("=" * 60)

    results = []
    for i, h in enumerate(escalated, 1):
        print(f"\n[{i}/{len(escalated)}] 探索孔洞: {h['hole_id']} (紧迫度: {h['urgency']})")
        try:
            result = explorer.force_explore(h['hole_id'], force_level="high")
            if result.get("crystal_generated"):
                print(f"   ✅ 生成晶体: {result['crystal_generated']}")
                results.append({"hole_id": h['hole_id'], "crystal_id": result['crystal_generated'], "status": "success"})
            else:
                print(f"   ⚠️ 失败: {result.get('error', '未知错误')}")
                results.append({"hole_id": h['hole_id'], "crystal_id": None, "status": "failed", "error": result.get('error', '未知错误')})
        except Exception as e:
            print(f"   ❌ 异常: {e}")
            results.append({"hole_id": h['hole_id'], "crystal_id": None, "status": "error", "error": str(e)})

        # 每处理3个等待1秒，避免过载
        if i % 3 == 0 and i < len(escalated):
            time.sleep(1)

    # 5. 汇总结果
    print("\n" + "=" * 60)
    print("📊 批量探索结果汇总")
    print("=" * 60)

    success_count = len([r for r in results if r["status"] == "success"])
    failed_count = len([r for r in results if r["status"] != "success"])

    print(f"   ✅ 成功: {success_count}")
    print(f"   ❌ 失败: {failed_count}")
    print("")

    if success_count > 0:
        print("   生成的晶体:")
        for r in results:
            if r["status"] == "success":
                print(f"      {r['hole_id']} -> {r['crystal_id']}")

    if failed_count > 0:
        print("   失败的孔洞:")
        for r in results:
            if r["status"] != "success":
                print(f"      {r['hole_id']}: {r.get('error', '未知错误')}")

    # 6. 查看最终状态
    print("\n" + "=" * 60)
    print("📊 最终状态")
    print("=" * 60)

    status = explorer.get_exploration_status()
    print(f"   总孔洞数: {status.get('total_holes', 0)}")
    print(f"   高优先级孔洞: {status.get('high_priority_holes', 0)}")
    print(f"   探索记录数: {status.get('exploration_log_count', 0)}")
    print(f"   待升级孔洞: {status.get('pending_escalation', 0)}")

    # 7. 检查 skills/ 目录
    skills_dir = Config.DATA_ROOT / "skills"
    if skills_dir.exists():
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("C")]
        print(f"\n   skills/ 目录: {len(skill_dirs)} 个 Skill")

    print("\n" + "=" * 60)
    print("✅ 批量强制探索完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()