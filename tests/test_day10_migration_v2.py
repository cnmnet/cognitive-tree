#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 10 测试：晶体代码化格式全面迁移 v2
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

from crystal_tree_all_in_one_day import Config, FileIO, CrystalEngine, Layer


class TestCrystalMigrationV2(unittest.TestCase):
    """晶体代码化格式迁移 v2 测试"""

    @classmethod
    def setUpClass(cls):
        cls.test_root = Path(tempfile.mkdtemp(prefix="test_migration_v2_"))
        cls.original_data_root = Config.DATA_ROOT
        Config.DATA_ROOT = cls.test_root

        FileIO.ensure_directories()
        FileIO.ensure_default_files()

        cls._create_test_crystals()
        cls.engine = CrystalEngine(FileIO())

    @classmethod
    def tearDownClass(cls):
        Config.DATA_ROOT = cls.original_data_root
        shutil.rmtree(cls.test_root, ignore_errors=True)

    @classmethod
    def _create_test_crystals(cls):
        """创建测试晶体数据"""
        crystals_content = """# 晶体卡片库

| ID | 内容 | 链接 | 输入条件 | 执行逻辑 | 输出格式 | 验证标准 |
|----|------|------|----------|----------|----------|----------|
| C001 | 认知晶体树的核心是动态分层存储机制 | C002,C003 | 用户输入问题 | 检索L1层晶体 | 返回相关晶体列表 | 返回结果非空 |
| C002 | 八道防线是系统的免疫系统 | C001 | 辩论进行中 | 触发警报规则 | 返回警报事件 | 警报需触发成功 |
| C003 | 沉思式反思包含四个维度 | C001 | 辩论结束 | 生成智慧回响 | 输出反思文本 | 文本长度>50字 |
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

    def test_01_migrate_all(self):
        """测试迁移所有晶体"""
        from scripts.migrate_crystals_to_skills_v2 import CrystalMigrationV2

        migrator = CrystalMigrationV2()
        migrator.data_root = self.test_root
        migrator.skills_root = self.test_root / "skills"
        migrator.crystals_file = self.test_root / "晶体数据" / "晶体卡片.md"
        migrator.layer_state_file = self.test_root / "系统日志" / "晶体分层.json"
        migrator.backup_dir = self.test_root / "系统日志" / "迁移备份"

        result = migrator.run()

        self.assertTrue(result["success"])
        self.assertEqual(result["migrated"], 3)

        # 验证目录结构
        skills_dir = self.test_root / "skills"
        self.assertTrue(skills_dir.exists())

        for cid in ["C001", "C002", "C003"]:
            skill_dir = skills_dir / cid
            self.assertTrue(skill_dir.exists())
            self.assertTrue((skill_dir / "CRYSTAL.md").exists())
            self.assertTrue((skill_dir / "validate.py").exists())
            self.assertTrue((skill_dir / "references").exists())

        print("[OK] 测试1: 迁移所有晶体通过")

    def test_02_parse_from_skills(self):
        """测试从 skills 目录解析晶体"""
        # 先执行迁移
        self.test_01_migrate_all()

        # 重新初始化引擎（清除缓存）
        self.engine = CrystalEngine(FileIO())

        crystals = self.engine.parse_crystals()
        self.assertEqual(len(crystals), 3)

        # 验证 C001 的内容
        c001 = next((c for c in crystals if c.id == "C001"), None)
        self.assertIsNotNone(c001)
        self.assertIn("动态分层存储机制", c001.content)
        self.assertIn("C002", c001.links)
        self.assertIn("C003", c001.links)

        print("[OK] 测试2: 从skills解析晶体通过")

    def test_03_crystal_md_format(self):
        """测试 CRYSTAL.md 格式完整"""
        self.test_01_migrate_all()

        crystal_md_path = self.test_root / "skills" / "C001" / "CRYSTAL.md"
        content = crystal_md_path.read_text(encoding='utf-8')

        # 检查所有必需的章节
        required_sections = [
            "## 基本信息",
            "## 核心内容",
            "## 链接关系",
            "## 代码化字段",
            "### 输入条件",
            "### 执行逻辑",
            "### 输出格式",
            "### 验证标准",
            "## 使用说明",
            "## 元数据"
        ]

        for section in required_sections:
            self.assertIn(section, content, f"缺少章节: {section}")

        print("[OK] 测试3: CRYSTAL.md格式完整通过")

    def test_04_validate_py_format(self):
        """测试 validate.py 格式完整"""
        self.test_01_migrate_all()

        validate_path = self.test_root / "skills" / "C001" / "validate.py"
        content = validate_path.read_text(encoding='utf-8')

        # 检查关键函数
        self.assertIn("def test_content_not_empty", content)
        self.assertIn("def test_input_conditions", content)
        self.assertIn("def test_validation_criteria", content)
        self.assertIn("def main", content)
        self.assertIn('if __name__ == "__main__":', content)

        print("[OK] 测试4: validate.py格式完整通过")

    def test_05_backup_created(self):
        """测试备份目录已创建"""
        self.test_01_migrate_all()

        backup_dir = self.test_root / "系统日志" / "迁移备份"
        self.assertTrue(backup_dir.exists())

        # 检查备份内容
        backup_contents = list(backup_dir.iterdir())
        self.assertGreater(len(backup_contents), 0)

        print("[OK] 测试5: 备份目录已创建通过")

    def test_06_crystal_links_preserved(self):
        """测试链接关系被保留"""
        self.test_01_migrate_all()

        self.engine = CrystalEngine(FileIO())
        crystals = self.engine.parse_crystals()

        # 验证 C001 的链接
        c001 = next((c for c in crystals if c.id == "C001"), None)
        self.assertIsNotNone(c001)
        self.assertEqual(len(c001.links), 2)
        self.assertIn("C002", c001.links)
        self.assertIn("C003", c001.links)

        # 验证 C002 的链接
        c002 = next((c for c in crystals if c.id == "C002"), None)
        self.assertIsNotNone(c002)
        self.assertEqual(len(c002.links), 1)
        self.assertIn("C001", c002.links)

        print("[OK] 测试6: 链接关系被保留通过")

    def test_07_validate_skill_works(self):
        """测试迁移后验证功能正常工作"""
        self.test_01_migrate_all()

        result = self.engine.validate_skill("C001")
        self.assertTrue(result["valid"])
        self.assertEqual(result["crystal_id"], "C001")
        self.assertIn("All validation passed", result["output"])

        print("[OK] 测试7: 验证功能正常工作通过")


def run_tests():
    print("=" * 60)
    print("Day 10 晶体代码化格式全面迁移测试")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCrystalMigrationV2)

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