#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 20 功能测试
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from crystal_tree_all_in_one_day import Config, CrystalEngine, FileIO, AIClient
from github_trending import GitHubTrendingCrystalizer

def test_github_trending():
    """测试 Trending 抓取（使用模拟数据）"""
    print("=== 测试 GitHub Trending 抓取 ===")
    engine = CrystalEngine(FileIO())
    ai = AIClient()
    crystalizer = GitHubTrendingCrystalizer(engine, ai)

    # 运行每日抓取
    result = crystalizer.run_daily(max_items=3)
    assert result["status"] == "success"
    assert len(result["crystals"]) > 0
    print(f"✅ 抓取成功：{result['message']}")

    # 检查保存的晶体
    crystals = crystalizer.get_trending_crystals(limit=5)
    assert len(crystals) > 0
    print(f"✅ 已保存 {len(crystals)} 个 Trending 晶体")
    for c in crystals[:3]:
        print(f"  - {c.get('id')}: {c.get('content')[:50]}...")

def test_engine_integration():
    """测试 CrystalEngine 集成"""
    print("\n=== 测试 CrystalEngine 集成 ===")
    engine = CrystalEngine(FileIO())
    # 确保方法存在
    assert hasattr(engine, 'get_github_trending_crystals')
    assert hasattr(engine, 'run_github_trending_daily')
    print("✅ 方法存在")

    # 调用
    crystals = engine.get_github_trending_crystals(limit=3)
    print(f"✅ 获取到 {len(crystals)} 个晶体")

if __name__ == "__main__":
    test_github_trending()
    test_engine_integration()
    print("\n所有测试通过！")