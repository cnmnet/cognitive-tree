#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 7 功能测试脚本
测试帕累托前沿跟踪系统和认知效率仪表盘
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from crystal_tree_all_in_one import (
    Config, FileIO, CrystalEngine, MetaLayer
)


def test_pareto_config():
    """测试帕累托配置是否存在"""
    print("\n" + "=" * 60)
    print("测试 1：帕累托配置检查")
    print("=" * 60)

    assert hasattr(Config, "PROFILE_HIGH_ACCURACY"), "缺少 PROFILE_HIGH_ACCURACY"
    assert hasattr(Config, "PROFILE_BALANCED"), "缺少 PROFILE_BALANCED"
    assert hasattr(Config, "PROFILE_ECONOMY"), "缺少 PROFILE_ECONOMY"
    assert hasattr(Config, "DEFAULT_PROFILE"), "缺少 DEFAULT_PROFILE"

    print(f"✅ 高精度模式：{Config.PROFILE_HIGH_ACCURACY['name']}")
    print(f"✅ 平衡模式：{Config.PROFILE_BALANCED['name']}")
    print(f"✅ 经济模式：{Config.PROFILE_ECONOMY['name']}")
    print(f"✅ 默认模式：{Config.DEFAULT_PROFILE}")


def test_pareto_tracker():
    """测试帕累托跟踪器"""
    print("\n" + "=" * 60)
    print("测试 2：帕累托跟踪器")
    print("=" * 60)

    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())
    meta = MetaLayer(engine, FileIO())

    # 记录测试数据
    test_data = [
        ("high_accuracy", 0.85, 0.005, 30.5, 5, 0.85),
        ("balanced", 0.72, 0.002, 15.2, 3, 0.72),
        ("economy", 0.55, 0.0008, 8.1, 1, 0.55),
    ]

    for profile, acc, cost, lat, refs, quality in test_data:
        meta.record_conversation_metrics(profile, acc, cost, lat, refs, quality)

    # 获取状态
    status = meta.get_pareto_status()
    print(f"配置数：{len(status.get('configs', {}))}")
    print(f"历史记录数：{status.get('history_count', 0)}")
    print(f"最优配置：{status.get('best_profile', '无')}")

    assert status.get('history_count', 0) >= 3, "历史记录不足"
    assert status.get('best_profile') in ['high_accuracy', 'balanced', 'economy'], "最优配置无效"

    print("✅ 帕累托跟踪器工作正常")


def test_daily_stats():
    """测试每日统计"""
    print("\n" + "=" * 60)
    print("测试 3：每日统计")
    print("=" * 60)

    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())
    meta = MetaLayer(engine, FileIO())

    # 记录多天数据
    for i in range(7):
        date = (datetime.now().date() - timedelta(days=i)).isoformat()
        meta.record_daily_stats({
            "date": date,
            "quality_score": 0.5 + i * 0.05,
            "crystal_refs": i + 1,
            "bias_index": 0.5 - i * 0.02,
            "tokens_used": 1000 + i * 100
        })

    daily_stats = meta.get_daily_stats(days=7)
    print(f"获取到 {len(daily_stats)} 天的数据")

    assert len(daily_stats) >= 1, "每日统计数据不足"

    for entry in daily_stats:
        print(f"  {entry.get('date')}: 质量={entry.get('quality_score'):.2f}, "
              f"引用={entry.get('crystal_refs')}, 偏差={entry.get('bias_index'):.2f}")

    print("✅ 每日统计工作正常")


def test_pareto_persistence():
    """测试帕累托数据持久化"""
    print("\n" + "=" * 60)
    print("测试 4：数据持久化")
    print("=" * 60)

    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())
    meta = MetaLayer(engine, FileIO())

    pareto_path = Config.DATA_ROOT / "系统日志" / "pareto_frontier.json"
    assert pareto_path.exists(), "帕累托文件未创建"

    # 读取并验证内容
    import json
    with open(pareto_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "configs" in data, "缺少 configs 字段"
    assert "history" in data, "缺少 history 字段"
    assert "daily_stats" in data, "缺少 daily_stats 字段"

    print(f"✅ 帕累托文件存在：{pareto_path}")
    print(f"   configs: {len(data.get('configs', {}))}")
    print(f"   history: {len(data.get('history', []))}")
    print(f"   daily_stats: {len(data.get('daily_stats', []))}")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Day 7 功能测试")
    print("=" * 60)

    try:
        test_pareto_config()
        test_pareto_tracker()
        test_daily_stats()
        test_pareto_persistence()

        print("\n" + "=" * 60)
        print("✅ 所有 Day 7 测试通过！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()