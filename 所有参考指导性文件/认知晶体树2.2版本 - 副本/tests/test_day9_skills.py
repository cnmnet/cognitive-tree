#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 9 测试：晶体→Skill 全面升级
"""

import sys
import os
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 先导入 Path
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import unittest
import tempfile
import shutil
from datetime import datetime

# 从主文件导入所有需要的类
from crystal_tree_all_in_one_day8 import Config, FileIO, CrystalEngine, DebateEngine, AIClient, Layer


class TestDay9Skills(unittest.TestCase):
    """Day 9 功能测试"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        # 创建测试数据目录
        cls.test_root = Path(tempfile.mkdtemp(prefix="test_day9_"))
        cls.original_data_root = Config.DATA_ROOT
        
        # 设置测试数据根目录
        Config.DATA_ROOT = cls.test_root
        
        # 确保目录存在
        FileIO.ensure_directories()
        FileIO.ensure_default_files()
        
        # 创建测试晶体数据
        cls._create_test_crystals()
        
        # 初始化引擎
        cls.engine = CrystalEngine(FileIO())
    
    @classmethod
    def tearDownClass(cls):
        """清理测试环境"""
        # 恢复原始数据根目录
        Config.DATA_ROOT = cls.original_data_root
        # 注释掉删除，保留临时目录用于调试
        # shutil.rmtree(cls.test_root, ignore_errors=True)
        print(f"\n[DEBUG] 临时目录保留: {cls.test_root}")
    
    @classmethod
    def _create_test_crystals(cls):
        """创建测试晶体数据"""
        crystals_content = """# 晶体卡片库

| ID | 内容 | 链接 | 输入条件 | 执行逻辑 | 输出格式 | 验证标准 |
|----|------|------|----------|----------|----------|----------|
| C001 | 认知晶体树的核心是动态分层存储机制 | C002,C003 | 用户输入问题 | 检索L1层晶体 | 返回相关晶体列表 | 返回结果非空 |
| C002 | 八道防线是系统的免疫系统 | C001 | 辩论进行中 | 触发警报规则 | 返回警报事件 | 警报需触发成功 |
| C003 | 沉思式反思包含四个维度 | C001 | 辩论结束 | 生成智慧回响 | 输出反思文本 | 文本长度大于50字 |
"""
        FileIO.write("crystals", crystals_content)
        
        # 创建分层状态
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
    
    def test_01_parse_crystals(self):
        """测试解析晶体"""
        crystals = self.engine.parse_crystals()
        self.assertEqual(len(crystals), 3)
        self.assertEqual(crystals[0].id, "C001")
        self.assertEqual(crystals[0].content, "认知晶体树的核心是动态分层存储机制")
        self.assertEqual(crystals[0].links, ["C002", "C003"])
        print("[OK] 测试1: 晶体解析通过")
    
    def test_02_migrate_to_skills(self):
        """测试迁移晶体到 Skill"""
        # 导入迁移脚本
        from scripts.migrate_crystals_to_skills import CrystalToSkillMigrator
        
        migrator = CrystalToSkillMigrator()
        # 使用测试数据根目录
        migrator.data_root = self.test_root
        migrator.skills_root = self.test_root / "skills"
        migrator.crystals_file = self.test_root / "晶体数据" / "晶体卡片.md"
        migrator.layer_state_file = self.test_root / "系统日志" / "晶体分层.json"
        
        # 执行迁移
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
        
        print("[OK] 测试2: 迁移到Skill通过")
    
    def test_03_get_skill_path(self):
        """测试获取 Skill 路径"""
        self.test_02_migrate_to_skills()
        
        path = self.engine.get_skill_path("C001")
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        
        path_none = self.engine.get_skill_path("C999")
        self.assertIsNone(path_none)
        print("[OK] 测试3: 获取Skill路径通过")
    
    def test_04_get_all_skills(self):
        """测试获取所有 Skill"""
        self.test_02_migrate_to_skills()
        
        skills = self.engine.get_all_skills()
        self.assertEqual(len(skills), 3)
        self.assertIn("C001", skills)
        self.assertIn("C002", skills)
        self.assertIn("C003", skills)
        print("[OK] 测试4: 获取所有Skill通过")
    
    def test_05_validate_skill(self):
        """测试验证 Skill"""
        self.test_02_migrate_to_skills()
        
        # 获取 skill 路径并打印
        skill_dir = self.engine.get_skill_path("C001")
        print(f"\n[DEBUG] Skill 路径: {skill_dir}")
        
        if skill_dir:
            validate_py = skill_dir / "validate.py"
            print(f"[DEBUG] validate.py 存在: {validate_py.exists()}")
            if validate_py.exists():
                content = validate_py.read_text(encoding='utf-8')
                print(f"[DEBUG] validate.py 内容前200字符:\n{content[:200]}")
        
        result = self.engine.validate_skill("C001")
        print(f"[DEBUG] 验证结果: {result}")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["crystal_id"], "C001")
        self.assertTrue(result["valid"])
    
    def test_06_validate_skills_batch(self):
        """测试批量验证 Skill"""
        self.test_02_migrate_to_skills()
        
        result = self.engine.validate_skills_batch(["C001", "C002"])
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["valid_count"], 2)
        self.assertIn("C001", result["results"])
        self.assertIn("C002", result["results"])
        print("[OK] 测试6: 批量验证Skill通过")
    
    def test_07_get_skill_crystal(self):
        """测试从 Skill 加载晶体"""
        self.test_02_migrate_to_skills()
        
        crystal = self.engine.get_skill_crystal("C001")
        self.assertIsNotNone(crystal)
        self.assertEqual(crystal.id, "C001")
        self.assertTrue(len(crystal.content) > 0)
        print("[OK] 测试7: 从Skill加载晶体通过")
    
    def test_08_get_skill_validation_summary(self):
        """测试获取 Skill 验证摘要"""
        self.test_02_migrate_to_skills()
        
        summary = self.engine.get_skill_validation_summary()
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["valid"], 3)
        self.assertEqual(summary["invalid"], 0)
        print("[OK] 测试8: 获取Skill验证摘要通过")
    
    def test_09_validate_py_content(self):
        """测试生成的 validate.py 内容"""
        self.test_02_migrate_to_skills()
        
        validate_path = self.test_root / "skills" / "C001" / "validate.py"
        self.assertTrue(validate_path.exists())
        
        content = validate_path.read_text(encoding='utf-8')
        self.assertIn("def test_content_not_empty", content)
        self.assertIn("def main", content)
        self.assertIn('if __name__ == "__main__":', content)
        print("[OK] 测试9: validate.py内容通过")
    
    def test_10_crystal_md_content(self):
        """测试生成的 CRYSTAL.md 内容"""
        self.test_02_migrate_to_skills()
        
        crystal_md_path = self.test_root / "skills" / "C001" / "CRYSTAL.md"
        self.assertTrue(crystal_md_path.exists())
        
        content = crystal_md_path.read_text(encoding='utf-8')
        self.assertIn("# C001 - 认知晶体", content)
        self.assertIn("## 核心内容", content)
        self.assertIn("认知晶体树的核心是动态分层存储机制", content)
        self.assertIn("## 链接关系", content)
        self.assertIn("C002", content)
        self.assertIn("C003", content)
        print("[OK] 测试10: CRYSTAL.md内容通过")


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Day 9 测试套件")
    print("=" * 60)
    print("")
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestDay9Skills)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("")
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