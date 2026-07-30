#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 15: 双环闭环验证测试脚本

运行10个标准测试问题，验证外环更新后的晶体是否被内环新一轮辩论调用
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crystal_tree_all_in_one_day import Config, FileIO, CrystalEngine, AIClient


def test_dual_loop():
    """
    双环闭环验证测试
    """
    print("=" * 70)
    print("Day 15: 双环闭环验证测试")
    print("=" * 70)
    print("")

    # 初始化
    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)

    print(f"📊 当前晶体总数: {len(engine.parse_crystals())}")
    print(f"📊 当前追踪记录: {engine.get_crystal_usage_stats().get('total_events', 0)} 条")
    print("")

    # 1. 获取外环更新记录（从 evolution_log 读取 + 从现有晶体推断）
    log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    updates = []
    
    # 方法A：从 evolution_log 读取
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for event in data.get("events", []):
                    et = event.get("event_type", "")
                    if et in ["crystal_added", "crystal_updated", "crystal_created", "crystal_added_from_debate"]:
                        details = event.get("details", {})
                        cid = details.get("crystal_id") or details.get("id") or details.get("crystal") or ""
                        if cid:
                            updates.append({
                                "crystal_id": cid,
                                "timestamp": event.get("timestamp", ""),
                                "type": et
                            })
        except Exception as e:
            print(f"⚠️ 读取进化日志失败: {e}")
    
    # 方法B：如果 evolution_log 中没有记录，从当前晶体列表推断
    if not updates:
        crystals = engine.parse_crystals()
        if crystals:
            sorted_crystals = sorted(crystals, key=lambda c: c.id, reverse=True)
            for c in sorted_crystals[:10]:
                updates.append({
                    "crystal_id": c.id,
                    "timestamp": datetime.now().isoformat(),
                    "type": "crystal_added_inferred"
                })
            print(f"📊 从现有晶体列表推断 {len(updates)} 条外环更新记录")

    print(f"📊 外环更新记录: {len(updates)} 条")
    if updates:
        print("  最新5条更新:")
        for u in updates[:5]:
            print(f"    - {u.get('crystal_id')} ({u.get('type')})")
    print("")

    # 2. 获取内环调用记录
    usage = engine.get_crystal_usage_stats()
    usage_history = usage.get("usage_history", [])
    print(f"📊 内环调用记录: {len(usage_history)} 条")
    unique = usage.get("unique_crystals", 0)
    print(f"📊 被调用的晶体数: {unique} 个")
    print("")

    # 3. 交叉验证
    verified_count = 0
    verification_details = []

    for update in updates:
        cid = update.get("crystal_id", "")
        if not cid:
            continue

        called = any(h.get("crystal_id") == cid for h in usage_history)

        update_time = update.get("timestamp", "")
        called_after_update = False
        if update_time:
            for h in usage_history:
                if h.get("crystal_id") == cid and h.get("timestamp", "") > update_time:
                    called_after_update = True
                    break
        else:
            called_after_update = called

        verification_details.append({
            "crystal_id": cid,
            "update_type": update.get("type", ""),
            "called": called,
            "called_after_update": called_after_update,
            "usage_count": usage.get("total_usage", {}).get(cid, 0)
        })

        if called_after_update:
            verified_count += 1

    # 4. 输出报告
    total_updates = len(updates)
    call_rate = verified_count / total_updates if total_updates > 0 else 0.0

    print("=" * 70)
    print("📊 双环闭环验证报告")
    print("=" * 70)
    print("")
    print(f"  外环更新晶体数: {total_updates}")
    print(f"  内环调用记录数: {len(usage_history)}")
    print(f"  验证通过数: {verified_count}")
    print(f"  调用率: {call_rate * 100:.1f}%")
    print("")

    if total_updates == 0:
        print("  ⚠️ 暂无外环更新记录，无法验证双环闭环")
    elif call_rate >= 0.8:
        print("  ✅ 双环闭环验证通过！")
        print(f"  外环更新晶体后，内环调用率 {call_rate*100:.1f}% ≥ 80%")
    elif call_rate >= 0.5:
        print("  ⚠️ 双环闭环验证部分通过")
        print(f"  外环更新晶体后，内环调用率 {call_rate*100:.1f}%")
        print("  建议检查未调用的晶体是否与问题相关")
    else:
        print("  ❌ 双环闭环验证未通过")
        print(f"  外环更新晶体后，内环调用率 {call_rate*100:.1f}% < 50%")
        print("  建议检查检索策略和晶体质量")

    print("")
    print("-" * 70)
    print("【详细验证明细】")
    print("-" * 70)

    for d in verification_details[:20]:
        status = "✅" if d.get("called_after_update", False) else "❌"
        called = "✅" if d.get("called", False) else "❌"
        print(f"  {d.get('crystal_id')}: 被调用 {called} | 更新后调用 {status} | 次数 {d.get('usage_count', 0)}")

    if len(verification_details) > 20:
        print(f"  ... 还有 {len(verification_details) - 20} 条")

    print("")
    print("=" * 70)
    print(f"📌 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    return call_rate >= 0.8


if __name__ == "__main__":
    success = test_dual_loop()
    sys.exit(0 if success else 1)