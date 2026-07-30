#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 6 功能测试脚本
测试 AGENTS.md 导出和 Skill 目录导出功能
"""

import sys
import tempfile
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from crystal_tree_all_in_one import Config, FileIO, CrystalEngine
from scripts.export_agents import AgentsExporter, export_agents_md, export_skill


def test_agents_md_generation():
    """测试 AGENTS.md 生成"""
    print("\n" + "=" * 60)
    print("测试 1：AGENTS.md 生成")
    print("=" * 60)

    # 初始化
    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())
    exporter = AgentsExporter(engine)

    # 生成内容
    content = exporter.generate_agents_md()
    assert len(content) > 100, "AGENTS.md 内容太短"
    assert "认知晶体树" in content, "AGENTS.md 缺少项目说明"
    assert "晶体卡片" in content or "核心晶体" in content, "AGENTS.md 缺少晶体卡片信息"

    print(f"✅ AGENTS.md 生成成功，长度：{len(content)} 字符")
    print(content[:500] + "\n...\n")


def test_skill_export():
    """测试单个 Skill 导出"""
    print("\n" + "=" * 60)
    print("测试 2：单个 Skill 目录导出")
    print("=" * 60)

    # 初始化
    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())

    # 先确保有晶体
    crystals = engine.parse_crystals()
    if not crystals:
        print("⚠️ 没有晶体，先创建一条测试晶体")
        FileIO.append("crystals", "\n| C001 | 测试晶体内容 | — |\n")
        engine = CrystalEngine(FileIO())
        crystals = engine.parse_crystals()

    crystal_id = crystals[0].id
    print(f"测试晶体 ID：{crystal_id}")

    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / f"skill_{crystal_id}"
        exporter = AgentsExporter(engine)
        result = exporter.export_skill_directory(crystal_id, output_dir)

        print(f"导出结果：{list(result.keys())}")

        # 验证文件存在
        assert (output_dir / "CRYSTAL.md").exists(), "CRYSTAL.md 未生成"
        assert (output_dir / "validate.py").exists(), "validate.py 未生成"
        assert (output_dir / "references").exists(), "references/ 目录未生成"

        print(f"✅ Skill 导出成功，目录：{output_dir}")
        for f in result.keys():
            print(f"  - {f}")


def test_batch_export():
    """测试批量导出"""
    print("\n" + "=" * 60)
    print("测试 3：批量导出全部 Skill")
    print("=" * 60)

    # 初始化
    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())
    exporter = AgentsExporter(engine)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = exporter.export_all_skills(Path(tmpdir), max_skills=5)

        print(f"批量导出结果：")
        print(f"  - 总晶体数：{result['total']}")
        print(f"  - 成功导出：{result['exported']}")
        print(f"  - 失败：{result['failed']}")
        print(f"  - AGENTS.md：{result.get('agents_md', '')}")

        # 验证 AGENTS.md 存在
        agents_path = Path(result.get('agents_md', ''))
        if agents_path.exists():
            print(f"  ✅ AGENTS.md 已生成：{agents_path}")
        else:
            print(f"  ⚠️ AGENTS.md 未生成")

        # 验证导出的 Skill 目录
        for detail in result.get("details", []):
            if detail.get("status") == "success":
                print(f"  ✅ {detail['id']}: {detail.get('files', [])[:3]}...")


def test_validate_script():
    """测试 validate.py 脚本功能"""
    print("\n" + "=" * 60)
    print("测试 4：validate.py 验证脚本")
    print("=" * 60)

    # 初始化
    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    engine = CrystalEngine(FileIO())
    exporter = AgentsExporter(engine)

    # 获取一个晶体
    crystals = engine.parse_crystals()
    if not crystals:
        print("⚠️ 没有晶体，跳过 validate.py 测试")
        return

    crystal_id = crystals[0].id

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / f"skill_{crystal_id}"
        exporter.export_skill_directory(crystal_id, output_dir)

        # 导入 validate.py 模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("validate", output_dir / "validate.py")
        validate_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validate_module)

        # 测试验证函数
        test_content = crystals[0].content
        result = validate_module.validate(test_content)

        print(f"验证结果：{'✅ 通过' if result['valid'] else '❌ 失败'}")
        print(f"得分：{result['score']}")
        print(f"检查项：{result['checks']}")
        if result['issues']:
            print(f"问题：{result['issues']}")

        assert isinstance(result, dict), "validate() 返回值不是字典"
        assert "valid" in result, "validate() 返回值缺少 valid 字段"
        assert "score" in result, "validate() 返回值缺少 score 字段"

        print("✅ validate.py 验证通过")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Day 6 功能测试")
    print("=" * 60)

    try:
        # 测试 1：AGENTS.md 生成
        test_agents_md_generation()

        # 测试 2：单个 Skill 导出
        test_skill_export()

        # 测试 3：批量导出
        test_batch_export()

        # 测试 4：validate.py 脚本
        test_validate_script()

        print("\n" + "=" * 60)
        print("✅ 所有 Day 6 测试通过！")
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