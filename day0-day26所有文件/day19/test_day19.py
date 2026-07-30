#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 19 功能测试
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

# 导入项目模块
from crystal_tree_all_in_one_day import Config, CrystalEngine, FileIO, AIClient
from scripts.export_agents import export_github_cognitive_tree, AgentsExporter
from self_healing import SelfHealing

def test_export_github_cognitive_tree():
    """测试导出 .github/cognitive-tree/ 目录"""
    print("\n=== 测试导出 .github/cognitive-tree/ 目录 ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = tmpdir
        files = FileIO()
        engine = CrystalEngine(files, ai_client=None)
        try:
            result_path = export_github_cognitive_tree(output_dir, engine)
            github_dir = Path(result_path)
            assert github_dir.exists(), "目录未创建"
            assert (github_dir / "rules.json").exists(), "rules.json 缺失"
            assert (github_dir / "skills").exists(), "skills 目录缺失"
            assert (github_dir / "prompts").exists(), "prompts 目录缺失"
            assert (github_dir / "README.md").exists(), "README.md 缺失"
            # 检查内容
            with open(github_dir / "rules.json", "r", encoding="utf-8") as f:
                rules = json.load(f)
                assert "defense_lines" in rules, "rules.json 格式错误"
            print("✅ 导出目录结构验证通过")
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            raise

def test_self_healing_basic():
    """测试自我修复基本功能（不触发实际修复）"""
    print("\n=== 测试自我修复基本功能 ===")
    files = FileIO()
    engine = CrystalEngine(files, ai_client=None)
    healer = SelfHealing(engine, ai_client=None, log_callback=print)
    # 模拟记录低质量
    healer.record_quality(0.3)  # 第一次低
    assert healer.consecutive_low_count == 1
    healer.record_quality(0.2)  # 第二次低
    assert healer.consecutive_low_count == 2
    healer.record_quality(0.1)  # 第三次低，应触发修复
    # 由于 engine.run_audit_now 可能未实现，但至少触发方法调用不报错
    # 我们只验证计数重置
    assert healer.consecutive_low_count == 0  # 修复后重置
    print("✅ 自我修复低质量触发测试通过")

    # 测试正常质量重置
    healer.consecutive_low_count = 2  # 模拟已有两次
    healer.record_quality(0.9)
    assert healer.consecutive_low_count == 0, "高质量应重置计数"
    print("✅ 高质量重置测试通过")

def main():
    print("开始 Day 19 功能测试...")
    test_export_github_cognitive_tree()
    test_self_healing_basic()
    print("\n所有测试通过！")

if __name__ == "__main__":
    main()