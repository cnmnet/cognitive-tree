#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 6: AGENTS.md 标准化导出模块
功能：
1. 从晶体卡片生成 AGENTS.md 格式
2. 导出为 Skill 目录（CRYSTAL.md + validate.py + references/）
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 导入主模块的类
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from crystal_tree_all_in_one import Config, CrystalEngine, FileIO


class AgentsExporter:
    """AGENTS.md 标准化导出器"""

    def __init__(self, engine: CrystalEngine = None):
        self.files = FileIO()
        self.engine = engine or CrystalEngine(self.files)
        self.template_content = self._load_template()

    def _load_template(self) -> str:
        """加载 AGENTS.md.template，如果不存在则使用默认模板"""
        template_path = Config.DATA_ROOT / "核心配置" / "AGENTS.md.template"
        if template_path.exists():
            try:
                return template_path.read_text(encoding="utf-8")
            except:
                pass

        # 默认模板
        return """# AGENTS.md - 认知晶体树项目规范

## 项目说明

本项目是一个认知晶体树系统，用于：
- 将用户输入晶体化为可复用的认知晶体
- 通过多角色辩论生成高质量决策建议
- 维护知识图谱和认知指纹

## 核心原则

1. **晶体化优先**：任何有价值的输入都应尝试晶体化
2. **引用必溯源**：所有输出必须引用晶体ID（Cxxx）或孔洞ID（Hxxx）
3. **辩论出真知**：复杂问题走多角色辩论流程
4. **持续进化**：系统通过八道防线和元层机制自我改进

## 禁止操作

1. 禁止凭空编造晶体ID
2. 禁止跳过G1/G2质量门
3. 禁止在无引用的情况下做出重大决策建议
4. 禁止忽略用户设定的认知指纹偏好

## 完成定义（Definition of Done）

- [ ] 用户问题已被清晰理解并分类
- [ ] 相关晶体已被检索并引用
- [ ] 输出包含至少1个晶体引用（格式：[Cxxx]）
- [ ] G2质量门已通过
- [ ] 输出被用户确认或采纳

## 质量检查清单

- [ ] 结论是否清晰？是否回答了用户问题？
- [ ] 引用是否充分？是否至少有1个晶体引用？
- [ ] 风险是否被识别？
- [ ] 是否有可执行的具体建议？
"""

    def generate_agents_md(self, include_crystals: bool = True, max_crystals: int = 50) -> str:
        """
        从晶体卡片生成 AGENTS.md 内容

        Args:
            include_crystals: 是否包含晶体卡片列表
            max_crystals: 最多包含多少条晶体

        Returns:
            AGENTS.md 格式的字符串
        """
        lines = [self.template_content]

        # 添加项目结构
        lines.append("\n## 项目结构\n")
        lines.append("```")
        lines.append("晶体树文件夹/")
        lines.append("├── 晶体数据/          # 晶体卡片库")
        lines.append("├── 核心配置/          # 系统配置文件")
        lines.append("├── 系统日志/          # 运行日志和状态")
        lines.append("├── 暂存区/            # 待确认卡片")
        lines.append("└── 模型缓存/          # 向量检索缓存")
        lines.append("```\n")

        if include_crystals:
            crystals = self.engine.parse_crystals()
            if crystals:
                lines.append("## 核心晶体卡片（认知资源）\n")
                lines.append("| ID | 内容摘要 | 链接 |")
                lines.append("|----|---------|------|")
                for c in crystals[:max_crystals]:
                    content = c.content[:60] + ("..." if len(c.content) > 60 else "")
                    links = ", ".join(c.links[:3]) + ("..." if len(c.links) > 3 else "")
                    lines.append(f"| {c.id} | {content} | {links or '—'} |")

                if len(crystals) > max_crystals:
                    lines.append(f"\n*（共 {len(crystals)} 条晶体，仅显示前 {max_crystals} 条）*")

        # 添加外部信源配置
        lines.append("\n## 外部信源配置\n")
        lines.append("| 信源 | 用途 |")
        lines.append("|------|------|")
        lines.append("| arXiv | AI/认知科学论文检索 |")
        lines.append("| HuggingFace | 模型/论文动态 |")
        lines.append("| 百度新闻 | 国产大模型动态 |")
        lines.append("| 全球认知雷达 | 多语言高质量内容 |")
        lines.append("| GitHub Trending | 开源项目认知晶体化 |\n")

        # 添加质量门配置
        lines.append("## 质量门配置\n")
        lines.append("| 质量门 | 阈值 | 说明 |")
        lines.append("|--------|------|------|")
        lines.append("| G1（问题可检验） | 匹配≥1条晶体/孔洞 | 确保问题与知识库相关 |")
        lines.append("| G2（输出可靠） | 引用≥2条 | 确保输出有据可查 |")
        lines.append("| 八道防线 | 引用率≥50% | 防止知识贫瘠 |\n")

        # 添加元原语配置
        lines.append("## 元原语配置\n")
        lines.append("| 元原语 | 状态 | 说明 |")
        lines.append("|--------|------|------|")
        meta_primitives = Config.META_PRIMITIVES
        for key, config in meta_primitives.items():
            status = "✅ 启用" if config.get("enabled", False) else "⏸️ 禁用"
            desc = config.get("description", "")
            lines.append(f"| {key} | {status} | {desc} |")

        # 添加生成时间
        lines.append(f"\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append(f"*数据根目录：{Config.DATA_ROOT}*")

        return "\n".join(lines)

    def export_skill_directory(self, crystal_id: str, output_dir: Path) -> Dict[str, str]:
        """
        导出单个晶体为 Skill 目录

        Args:
            crystal_id: 晶体ID（如 C001）
            output_dir: 输出目录

        Returns:
            Dict[str, str]: 生成的文件路径映射
        """
        crystals = self.engine.parse_crystals()
        crystal = next((c for c in crystals if c.id == crystal_id), None)
        if not crystal:
            return {"error": f"未找到晶体 {crystal_id}"}

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        # 1. CRYSTAL.md
        crystal_md_path = output_dir / "CRYSTAL.md"
        crystal_content = f"""# 晶体卡片：{crystal.id}

## 内容
{crystal.content}

## 链接
{", ".join(crystal.links) if crystal.links else "无"}

## 元数据
- 生成时间：{datetime.now().isoformat()}
- 层级：{crystal.layer.value if hasattr(crystal.layer, 'value') else str(crystal.layer)}
- 热度：{getattr(crystal, 'heat', 0.0)}
"""
        crystal_md_path.write_text(crystal_content, encoding="utf-8")
        result["CRYSTAL.md"] = str(crystal_md_path)

        # 2. validate.py
        validate_py_path = output_dir / "validate.py"
        validate_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
晶体验证脚本
由认知晶体树自动生成
"""

import sys
import re

def validate(content: str) -> dict:
    """
    验证晶体内容的有效性

    Returns:
        {
            "valid": bool,
            "checks": {
                "has_content": bool,
                "length_ok": bool,
                "has_links": bool,
                "no_invalid_chars": bool
            },
            "score": float,  # 0-1
            "issues": list[str]
        }
    """
    checks = {
        "has_content": bool(content and content.strip()),
        "length_ok": 10 <= len(content) <= 500,
        "has_links": bool(re.search(r'C\\d{3}|H\\d{3}', content)),
        "no_invalid_chars": not re.search(r'[<>{}]', content)
    }

    issues = []
    if not checks["has_content"]:
        issues.append("内容为空")
    if not checks["length_ok"]:
        issues.append(f"长度 {len(content)} 不在 10-500 范围内")
    if not checks["has_links"]:
        issues.append("缺少晶体链接（Cxxx）")
    if not checks["no_invalid_chars"]:
        issues.append("包含非法字符")

    score = sum(1 for v in checks.values() if v) / len(checks)
    valid = score >= 0.75 and checks["has_content"]

    return {
        "valid": valid,
        "checks": checks,
        "score": round(score, 2),
        "issues": issues
    }

if __name__ == "__main__":
    # 测试验证函数
    test_content = sys.argv[1] if len(sys.argv) > 1 else "这是测试内容 C001"
    result = validate(test_content)
    print(f"验证结果: {'✅ 通过' if result['valid'] else '❌ 失败'}")
    print(f"得分: {result['score']}")
    print(f"检查项: {result['checks']}")
    if result['issues']:
        print(f"问题: {result['issues']}")
'''
        validate_py_path.write_text(validate_content, encoding="utf-8")
        result["validate.py"] = str(validate_py_path)

        # 3. references/ 目录（如果晶体有链接则创建引用文件）
        refs_dir = output_dir / "references"
        if crystal.links:
            refs_dir.mkdir(exist_ok=True)
            for i, link in enumerate(crystal.links[:5]):
                ref_file = refs_dir / f"ref_{i+1}.md"
                ref_file.write_text(f"# 引用 {i+1}\n\n来源：{link}\n\n*此引用由认知晶体树自动提取*", encoding="utf-8")
                result[f"references/ref_{i+1}.md"] = str(ref_file)
        else:
            # 即使无链接也创建空目录
            refs_dir.mkdir(exist_ok=True)
            (refs_dir / "README.md").write_text("# 引用目录\n\n暂无外部引用", encoding="utf-8")
            result["references/README.md"] = str(refs_dir / "README.md")

        return result

    def export_all_skills(self, output_dir: Path, max_skills: int = 10) -> Dict[str, Any]:
        """
        导出所有晶体为 Skill 目录

        Args:
            output_dir: 输出根目录
            max_skills: 最多导出多少条

        Returns:
            导出结果统计
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        crystals = self.engine.parse_crystals()
        results = {
            "total": len(crystals),
            "exported": 0,
            "failed": 0,
            "details": []
        }

        for c in crystals[:max_skills]:
            skill_dir = output_dir / f"skill_{c.id}"
            try:
                result = self.export_skill_directory(c.id, skill_dir)
                if "error" in result:
                    results["failed"] += 1
                    results["details"].append({"id": c.id, "status": "failed", "error": result["error"]})
                else:
                    results["exported"] += 1
                    results["details"].append({"id": c.id, "status": "success", "files": list(result.keys())})
            except Exception as e:
                results["failed"] += 1
                results["details"].append({"id": c.id, "status": "failed", "error": str(e)})

        # 导出全局 AGENTS.md
        agents_content = self.generate_agents_md()
        (output_dir / "AGENTS.md").write_text(agents_content, encoding="utf-8")
        results["agents_md"] = str(output_dir / "AGENTS.md")

        return results


def export_agents_md(engine: CrystalEngine = None) -> str:
    """便捷函数：生成 AGENTS.md 内容"""
    exporter = AgentsExporter(engine)
    return exporter.generate_agents_md()


def export_skill(crystal_id: str, output_dir: str, engine: CrystalEngine = None) -> Dict[str, str]:
    """便捷函数：导出单个 Skill 目录"""
    exporter = AgentsExporter(engine)
    return exporter.export_skill_directory(crystal_id, Path(output_dir))