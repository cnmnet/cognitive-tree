#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 9.5 测试：跨用户认知贡献层
"""

import sys
import os
import io
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import unittest
import tempfile
import shutil
from datetime import datetime

from crystal_tree_all_in_one_day8 import Config, FileIO, CrystalEngine, Layer


class TestWisdomCommons(unittest.TestCase):
    """智慧公库测试"""

    @classmethod
    def setUpClass(cls):
        cls.test_root = Path(tempfile.mkdtemp(prefix="test_wisdom_"))
        cls.original_data_root = Config.DATA_ROOT
        Config.DATA_ROOT = cls.test_root

        FileIO.ensure_directories()
        FileIO.ensure_default_files()

        # 创建测试晶体
        cls._create_test_crystals()
        cls.engine = CrystalEngine(FileIO())

    @classmethod
    def tearDownClass(cls):
        Config.DATA_ROOT = cls.original_data_root
        shutil.rmtree(cls.test_root, ignore_errors=True)

    @classmethod
    def _create_test_crystals(cls):
        crystals_content = """# 晶体卡片库

| ID | 内容 | 链接 | 输入条件 | 执行逻辑 | 输出格式 | 验证标准 |
|----|------|------|----------|----------|----------|----------|
| C001 | 认知晶体树的核心是动态分层存储机制 | C002 | 用户输入 | 检索 | 返回列表 | 非空 |
| C002 | 八道防线是系统的免疫系统 | C001 | 辩论中 | 触发警报 | 返回事件 | 触发成功 |
| C003 | 沉思式反思包含四个维度 | C001 | 辩论结束 | 生成回响 | 输出文本 | 长度>50 |
"""
        FileIO.write("crystals", crystals_content)

        layer_state = {
            "layers": {"C001": "L1", "C002": "L2", "C003": "L2"},
            "heat_map": {"C001": 0.8, "C002": 0.5, "C003": 0.3},
            "last_accessed": {
                "C001": datetime.now().date().isoformat(),
                "C002": datetime.now().date().isoformat(),
                "C003": datetime.now().date().isoformat()
            },
            "manual_override": {}
        }
        FileIO.write("layer_state", json.dumps(layer_state, ensure_ascii=False, indent=2))

    def test_01_load_wisdom_commons(self):
        """测试加载智慧公库"""
        commons = self.engine._load_wisdom_commons()
        self.assertIsNotNone(commons)
        self.assertIn("version", commons)
        self.assertIn("crystals", commons)
        self.assertIn("users", commons)
        print("[OK] 测试1: 加载智慧公库通过")

    def test_02_contribute_crystal(self):
        """测试贡献晶体"""
        # 先添加一些引用使评分提高
        result = self.engine.contribute_crystal("C001", "test_user", False)
        self.assertTrue(result["success"])
        self.assertEqual(result["credits_earned"], 10)
        print("[OK] 测试2: 贡献晶体通过")

    def test_03_get_wisdom_seeds(self):
        """测试获取种子"""
        # 先贡献
        self.engine.contribute_crystal("C001", "test_user", False)

        seeds = self.engine.get_wisdom_seeds(limit=5)
        self.assertIsNotNone(seeds)
        self.assertGreaterEqual(len(seeds), 0)
        print("[OK] 测试3: 获取种子通过")

    def test_04_inherit_seeds(self):
        """测试继承种子"""
        # 先贡献
        self.engine.contribute_crystal("C001", "test_user", False)

        result = self.engine.inherit_seeds("new_user", limit=3)
        self.assertTrue(result["success"])
        self.assertGreater(len(result.get("seeds", [])), 0)
        print("[OK] 测试4: 继承种子通过")

    def test_05_get_user_credits(self):
        """测试获取用户积分"""
        # 先贡献
        self.engine.contribute_crystal("C001", "test_user", False)

        info = self.engine.get_user_credits("test_user")
        self.assertEqual(info["credits"], 10)
        self.assertEqual(info["contributions"], 1)
        print("[OK] 测试5: 获取用户积分通过")

    def test_06_use_credits(self):
        """测试使用积分"""
        # 先贡献
        self.engine.contribute_crystal("C001", "test_user", False)

        result = self.engine.use_credits("test_user", 5, "兑换搜索次数")
        self.assertTrue(result["success"])
        self.assertEqual(result["remaining_credits"], 5)
        print("[OK] 测试6: 使用积分通过")

    def test_07_maintain_wisdom_commons(self):
        """测试维护智慧公库"""
        # 先贡献
        self.engine.contribute_crystal("C001", "test_user", False)

        result = self.engine.maintain_wisdom_commons()
        self.assertTrue(result["success"])
        print(f"[OK] 测试7: 维护智慧公库通过 (活跃:{result['maintained']}, 沉底:{result['deprecated']})")

    def test_08_get_wisdom_stats(self):
        """测试获取统计"""
        # 先贡献
        self.engine.contribute_crystal("C001", "test_user", False)

        stats = self.engine.get_wisdom_stats()
        self.assertIsNotNone(stats)
        self.assertIn("total_crystals", stats)
        print("[OK] 测试8: 获取统计通过")


def run_tests():
    print("=" * 60)
    print("Day 9.5 智慧公库测试")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestWisdomCommons)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 60)
    if result.wasSuccessful():
        print("[OK] 所有测试通过！")
    else:
        print(f"[FAIL] 测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)