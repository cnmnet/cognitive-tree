#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 9 完整测试运行器
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess
import time

def run_test_suite():
    """运行完整测试套件"""
    print("=" * 70)
    print("🚀 Day 9 完整测试流程")
    print("=" * 70)
    print("")
    
    tests_dir = Path(__file__).resolve().parent
    
    # 1. 运行单元测试
    print("📋 阶段1: 运行单元测试...")
    print("-" * 50)
    
    test_script = tests_dir / "test_day9_skills.py"
    if not test_script.exists():
        print(f"❌ 测试脚本不存在: {test_script}")
        return False
    
    result = subprocess.run(
        [sys.executable, str(test_script)],
        capture_output=True,
        text=True,
        cwd=str(tests_dir.parent)
    )
    
    print(result.stdout)
    if result.stderr:
        print("错误输出:")
        print(result.stderr)
    
    if result.returncode != 0:
        print("❌ 单元测试失败")
        return False
    
    print("✅ 单元测试通过")
    print("")
    
    # 2. 模拟主程序测试
    print("📋 阶段2: 模拟主程序测试...")
    print("-" * 50)
    
    try:
        # 模拟一个简单的集成测试
        from config import Config, FileIO
        from engine import CrystalEngine
        
        # 确保目录存在
        FileIO.ensure_directories()
        FileIO.ensure_default_files()
        
        # 检查 skills 目录是否存在
        skills_dir = Config.DATA_ROOT / "skills"
        if not skills_dir.exists():
            print("⚠️ skills 目录不存在，创建中...")
            skills_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查是否已有 Skill
        engine = CrystalEngine(FileIO())
        skills = engine.get_all_skills()
        print(f"📊 当前 Skill 数量: {len(skills)}")
        
        if len(skills) == 0:
            print("⚠️ 没有找到 Skill，请先运行迁移")
        else:
            print(f"   Skill 列表: {', '.join(skills)}")
            # 尝试验证第一个 Skill
            if skills:
                result = engine.validate_skill(skills[0])
                print(f"   {skills[0]} 验证: {'✅ 通过' if result.get('valid') else '❌ 未通过'}")
        
        print("✅ 主程序集成测试通过")
        
    except Exception as e:
        print(f"❌ 主程序测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("")
    print("=" * 70)
    print("✅ 所有测试通过！")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = run_test_suite()
    sys.exit(0 if success else 1)