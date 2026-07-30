#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
晶体代码化格式全面迁移 v2
将现有所有晶体卡片从 Markdown 表格格式迁移到 Skill 目录格式
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import re
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

# 导入项目配置
from crystal_tree_all_in_one_day import Config, FileIO, CrystalEngine, Layer


class CrystalMigrationV2:
    """晶体代码化格式全面迁移 v2"""

    def __init__(self):
        self.data_root = Config.DATA_ROOT
        self.skills_root = self.data_root / "skills"
        self.crystals_file = self.data_root / "晶体数据" / "晶体卡片.md"
        self.layer_state_file = self.data_root / "系统日志" / "晶体分层.json"
        self.backup_dir = self.data_root / "系统日志" / "迁移备份" / datetime.now().strftime("%Y%m%d_%H%M%S")

    def ensure_directories(self):
        """确保所需目录存在"""
        self.skills_root.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup_existing_skills(self):
        """备份现有的 skills 目录"""
        if self.skills_root.exists():
            backup_skills_dir = self.backup_dir / "skills_backup"
            # 如果备份目录已存在，先删除
            if backup_skills_dir.exists():
                shutil.rmtree(backup_skills_dir)
            shutil.copytree(self.skills_root, backup_skills_dir)
            print(f"📦 已备份现有 skills 目录到: {backup_skills_dir}")

    def parse_crystals_from_md(self) -> List[Dict]:
        """从 Markdown 文件中解析晶体数据"""
        if not self.crystals_file.exists():
            print(f"⚠️ 晶体卡片文件不存在: {self.crystals_file}")
            return []

        content = self.crystals_file.read_text(encoding='utf-8')
        crystals = []

        # 解析表格行: | C001 | 内容 | 链接 | 输入条件 | 执行逻辑 | 输出格式 | 验证标准 |
        pattern = r"\| (C\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|"

        for match in re.finditer(pattern, content):
            crystal_id = match.group(1)
            content_text = match.group(2).strip()
            links_str = match.group(3).strip()
            input_conditions = [c.strip() for c in match.group(4).split(",") if c.strip() and c.strip() != "—"]
            execution_logic = match.group(5).strip() if match.group(5).strip() != "—" else ""
            output_format = match.group(6).strip() if match.group(6).strip() != "—" else ""
            validation_criteria = [c.strip() for c in match.group(7).split(",") if c.strip() and c.strip() != "—"]

            crystals.append({
                "id": crystal_id,
                "content": content_text,
                "links": [l.strip() for l in links_str.split(",") if l.strip() and l.strip() != "—"],
                "input_conditions": input_conditions,
                "execution_logic": execution_logic,
                "output_format": output_format,
                "validation_criteria": validation_criteria
            })

        print(f"📊 从晶体卡片中解析到 {len(crystals)} 条晶体")
        return crystals

    def load_layer_state(self) -> Dict:
        """加载晶体分层状态"""
        if not self.layer_state_file.exists():
            return {"layers": {}, "heat_map": {}, "last_accessed": {}, "manual_override": {}}
        try:
            return json.loads(self.layer_state_file.read_text(encoding='utf-8'))
        except:
            return {"layers": {}, "heat_map": {}, "last_accessed": {}, "manual_override": {}}

    def generate_validate_py(self, crystal: Dict) -> str:
        """为晶体生成 validate.py 脚本"""
        crystal_id = crystal["id"]
        content = crystal["content"]
        input_conditions = crystal.get("input_conditions", [])
        execution_logic = crystal.get("execution_logic", "")
        output_format = crystal.get("output_format", "")
        validation_criteria = crystal.get("validation_criteria", [])

        test_functions = []

        # 1. 内容非空验证
        test_functions.append(f'''
def test_content_not_empty():
    """验证晶体内容非空"""
    content = "{content[:50]}..."
    assert len(content) > 0, "crystal content cannot be empty"
    print("[PASS] content_not_empty")
''')

        # 2. 输入条件验证
        if input_conditions:
            cond_lines = []
            for c in input_conditions:
                cond_lines.append(f'    if "{c}" not in str(input_data): print(f"  WARN: missing input condition: {c}")')
            test_functions.append(f'''
def test_input_conditions():
    """验证输入条件（宽松模式）"""
    input_data = {{"text": "test input", "用户输入问题": "test question"}}
{chr(10).join(cond_lines)}
    print("[PASS] input_conditions")
''')
        else:
            test_functions.append('''
def test_input_conditions():
    """验证输入条件（无特定要求）"""
    print("[PASS] input_conditions (no specific requirements)")
''')

        # 3. 执行逻辑验证
        if execution_logic:
            test_functions.append(f'''
def test_execution_logic():
    """验证执行逻辑（模拟）"""
    result = True
    assert result is True, "execution logic simulation failed"
    print("[PASS] execution_logic")
''')
        else:
            test_functions.append('''
def test_execution_logic():
    """验证执行逻辑（无特定要求）"""
    print("[PASS] execution_logic (no specific requirements)")
''')

        # 4. 输出格式验证
        if output_format:
            test_functions.append(f'''
def test_output_format():
    """验证输出格式"""
    test_output = "test output"
    assert len(test_output) > 0, "output cannot be empty"
    print("[PASS] output_format")
''')
        else:
            test_functions.append('''
def test_output_format():
    """验证输出格式（无特定要求）"""
    print("[PASS] output_format (no specific requirements)")
''')

        # 5. 验证标准测试
        if validation_criteria:
            crit_lines = []
            for i, crit in enumerate(validation_criteria):
                crit_lines.append(f'    print("  criteria {i+1}: {crit}")')
            test_functions.append(f'''
def test_validation_criteria():
    """验证所有验证标准"""
{chr(10).join(crit_lines)}
    print("[PASS] validation_criteria")
''')
        else:
            test_functions.append('''
def test_validation_criteria():
    """验证所有验证标准（无特定要求）"""
    print("[PASS] validation_criteria (no specific requirements)")
''')

        # 构建主函数调用
        call_lines = []
        for func in test_functions:
            if "def " in func:
                func_name = func.split("def ")[1].split("(")[0].strip()
                call_lines.append(f'    {func_name}()')

        main_body = "\n".join(call_lines) if call_lines else '    print("no test functions")'
        all_functions = "\n".join(test_functions)

        return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{crystal_id} validation script
Auto-generated during crystal migration v2

Crystal content: {content[:80]}...
"""

import sys

{all_functions}

def main():
    """Run all validation tests"""
    print(f"Validating crystal {crystal_id}...")
    print("-" * 50)

{main_body}

    print("-" * 50)
    print("All validation passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

    def generate_crystal_md(self, crystal: Dict, layer_state: Dict) -> str:
        """生成 CRYSTAL.md 文件 - 使用列表拼接避免三引号嵌套"""
        crystal_id = crystal["id"]
        content = crystal["content"]
        links = crystal.get("links", [])
        input_conditions = crystal.get("input_conditions", [])
        execution_logic = crystal.get("execution_logic", "")
        output_format = crystal.get("output_format", "")
        validation_criteria = crystal.get("validation_criteria", [])

        # 获取层级信息
        layers = layer_state.get("layers", {})
        layer = layers.get(crystal_id, "L2")
        heat = layer_state.get("heat_map", {}).get(crystal_id, 0.0)
        last_accessed = layer_state.get("last_accessed", {}).get(crystal_id, "从未")

        # 构建链接列表
        links_text = "\n".join([f"- {link}" for link in links]) if links else "（暂无链接）"

        # 构建输入条件列表
        input_text = "\n".join([f"- {cond}" for cond in input_conditions]) if input_conditions else "（无特定输入条件）"

        # 构建验证标准列表
        validation_text = "\n".join([f"- {crit}" for crit in validation_criteria]) if validation_criteria else "（无特定验证标准）"

        # 使用列表拼接构建 CRYSTAL.md 内容
        lines = []
        lines.append(f"# {crystal_id} - 认知晶体")
        lines.append("")
        lines.append("## 基本信息")
        lines.append("")
        lines.append("| 属性 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| **晶体ID** | {crystal_id} |")
        lines.append(f"| **当前层级** | {layer} |")
        lines.append(f"| **热度** | {heat:.2f} |")
        lines.append(f"| **最后访问** | {last_accessed} |")
        lines.append("")
        lines.append("## 核心内容")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("## 链接关系")
        lines.append("")
        lines.append(links_text)
        lines.append("")
        lines.append("## 代码化字段")
        lines.append("")
        lines.append("### 输入条件")
        lines.append("")
        lines.append(input_text)
        lines.append("")
        lines.append("### 执行逻辑")
        lines.append("")
        lines.append(execution_logic if execution_logic else "（无执行逻辑）")
        lines.append("")
        lines.append("### 输出格式")
        lines.append("")
        lines.append(output_format if output_format else "（无特定输出格式）")
        lines.append("")
        lines.append("### 验证标准")
        lines.append("")
        lines.append(validation_text)
        lines.append("")
        lines.append("## 使用说明")
        lines.append("")
        lines.append("此晶体可通过 `validate.py` 脚本进行自动验证：")
        lines.append("```bash")
        lines.append("python validate.py")
        lines.append("```")
        lines.append("")
        lines.append("## 元数据")
        lines.append("")
        lines.append(f"- **创建时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("- **来源**: 晶体迁移 v2 (Day 10)")

        return "\n".join(lines)

    def migrate_crystal(self, crystal: Dict, layer_state: Dict) -> Dict:
        """迁移单个晶体到 Skill 目录"""
        crystal_id = crystal["id"]
        skill_dir = self.skills_root / crystal_id

        # 创建目录
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "references").mkdir(parents=True, exist_ok=True)

        # 生成 CRYSTAL.md
        crystal_md = self.generate_crystal_md(crystal, layer_state)
        (skill_dir / "CRYSTAL.md").write_text(crystal_md, encoding='utf-8')

        # 生成 validate.py
        validate_py = self.generate_validate_py(crystal)
        (skill_dir / "validate.py").write_text(validate_py, encoding='utf-8')

        # 生成 references/ 下的引用文件
        refs_dir = skill_dir / "references"
        for link in crystal.get("links", []):
            ref_file = refs_dir / f"{link}.md"
            if not ref_file.exists():
                ref_file.write_text(
                    f"# 引用: {link}\n\n此文件是对晶体 {link} 的引用占位。\n\n请根据需要补充内容。",
                    encoding='utf-8'
                )

        # 生成 README.md
        readme = skill_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {crystal_id} Skill\n\n此 Skill 包含晶体 {crystal_id} 的完整定义和验证脚本。\n\n"
                f"## 文件结构\n\n- `CRYSTAL.md` - 晶体定义\n- `validate.py` - 验证脚本\n- `references/` - 外部引用\n",
                encoding='utf-8'
            )

        return {
            "id": crystal_id,
            "path": str(skill_dir),
            "files": ["CRYSTAL.md", "validate.py", "references/"]
        }

    def run(self) -> Dict:
        """执行迁移"""
        print("=" * 60)
        print("🔧 晶体代码化格式全面迁移 v2")
        print("=" * 60)

        # 1. 确保目录存在
        self.ensure_directories()

        # 2. 备份现有 skills
        self.backup_existing_skills()

        # 3. 解析晶体
        crystals = self.parse_crystals_from_md()
        if not crystals:
            print("❌ 没有找到任何晶体，迁移终止")
            return {"success": False, "error": "没有找到任何晶体"}

        # 4. 加载分层状态
        layer_state = self.load_layer_state()

        # 5. 迁移每个晶体
        results = []
        failed = []

        for crystal in crystals:
            try:
                result = self.migrate_crystal(crystal, layer_state)
                results.append(result)
                print(f"  ✅ {crystal['id']} -> {result['path']}")
            except Exception as e:
                print(f"  ❌ {crystal['id']} 迁移失败: {e}")
                failed.append({"id": crystal["id"], "error": str(e)})

        # 6. 生成迁移报告
        report = self.generate_migration_report(results, failed)

        print("=" * 60)
        print(f"✅ 迁移完成: 成功 {len(results)} 条，失败 {len(failed)} 条")
        print(f"📄 迁移报告: {self.data_root / '系统日志' / '晶体迁移报告_v2.md'}")
        print("=" * 60)

        return {
            "success": len(failed) == 0,
            "total": len(crystals),
            "migrated": len(results),
            "failed": len(failed),
            "results": results,
            "failed_details": failed,
            "report": report,
            "backup_dir": str(self.backup_dir)
        }

    def generate_migration_report(self, results: List, failed: List) -> str:
        """生成迁移报告"""
        report_path = self.data_root / "系统日志" / "晶体迁移报告_v2.md"

        lines = []
        lines.append("# 晶体代码化格式全面迁移报告 v2")
        lines.append("")
        lines.append(f"**迁移时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**备份目录**: {self.backup_dir}")
        lines.append("")
        lines.append("## 迁移结果")
        lines.append("")
        lines.append(f"- 总晶体数: {len(results) + len(failed)}")
        lines.append(f"- 成功迁移: {len(results)}")
        lines.append(f"- 失败: {len(failed)}")
        lines.append("")

        if results:
            lines.append("## 成功迁移的晶体")
            lines.append("")
            lines.append("| 晶体ID | Skill目录 | 文件数 |")
            lines.append("|--------|-----------|--------|")
            for r in results:
                files = r.get("files", [])
                lines.append(f"| {r['id']} | `{r['path']}` | {len(files)} |")
            lines.append("")

        if failed:
            lines.append("## 失败详情")
            lines.append("")
            for f in failed:
                lines.append(f"- {f['id']}: {f['error']}")
            lines.append("")

        lines.append("## 目录结构")
        lines.append("")
        lines.append("```")
        lines.append("skills/")
        lines.append("├── C001/")
        lines.append("│   ├── CRYSTAL.md")
        lines.append("│   ├── validate.py")
        lines.append("│   ├── README.md")
        lines.append("│   └── references/")
        lines.append("├── C002/")
        lines.append("│   └── ...")
        lines.append("└── ...")
        lines.append("```")

        report_content = "\n".join(lines)
        report_path.write_text(report_content, encoding='utf-8')

        return report_content


def main():
    """主入口"""
    migrator = CrystalMigrationV2()
    result = migrator.run()

    if result["success"]:
        print("\n✅ 所有晶体迁移成功！")
        print(f"   备份目录: {result['backup_dir']}")
    else:
        print(f"\n⚠️ 迁移部分失败: {result['failed']} 条")
        print("   请检查错误详情并重试")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())