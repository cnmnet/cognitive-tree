#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速贡献晶体到智慧公库
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from crystal_tree_all_in_one_day8 import CrystalEngine, FileIO, Config

def main():
    print("=" * 60)
    print("🌐 快速贡献晶体到智慧公库")
    print("=" * 60)
    
    # 初始化引擎
    engine = CrystalEngine(FileIO())
    
    # 1. 查看所有晶体
    crystals = engine.parse_crystals()
    print(f"\n📊 当前共有 {len(crystals)} 条晶体")
    
    # 2. 选择要贡献的晶体（选择第一个）
    if not crystals:
        print("❌ 没有找到任何晶体")
        return
    
    # 显示前5个晶体
    print("\n📋 晶体列表（前5个）：")
    for i, c in enumerate(crystals[:5]):
        print(f"  {i+1}. {c.id}: {c.content[:40]}...")
    
    # 3. 贡献晶体 C001
    crystal_id = "C001"
    print(f"\n⭐ 正在贡献晶体 {crystal_id}...")
    
    result = engine.contribute_crystal(crystal_id, "gui_user", is_anonymous=True)
    
    if result.get("success"):
        print(f"✅ {result.get('message')}")
        print(f"   获得 {result.get('credits_earned', 0)} 积分")
        print(f"   当前总积分: {result.get('total_credits', 0)}")
        print(f"   公库晶体总数: {result.get('total_crystals', 0)}")
    else:
        print(f"⚠️ 贡献失败: {result.get('error', '未知错误')}")
        print(f"   评分: {result.get('score', 'N/A')}")
    
    # 4. 查看公库状态
    print("\n📊 智慧公库状态:")
    stats = engine.get_wisdom_stats()
    print(f"   总晶体数: {stats.get('total_crystals', 0)}")
    print(f"   活跃晶体: {stats.get('active_crystals', 0)}")
    print(f"   总积分池: {stats.get('total_credits', 0)}")
    
    # 5. 查看种子
    seeds = engine.get_wisdom_seeds(limit=5)
    print(f"\n🌱 公库种子（{len(seeds)} 条）:")
    for seed in seeds:
        print(f"   - {seed.get('crystal_id')}: {seed.get('content', '')[:40]}... (使用: {seed.get('usage_count', 0)}次)")

if __name__ == "__main__":
    main()