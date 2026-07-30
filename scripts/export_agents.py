#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 6: AGENTS.md 标准化导出模块
功能：
1. 从晶体卡片生成 AGENTS.md 格式
2. 导出为 Skill 目录（CRYSTAL.md + validate.py + references/）
Day 19 升级：支持 .github/cognitive-tree/ 目录规范，导出全部技能
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 导入主模块的类
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from crystal_tree_all_in_one_day import Config, CrystalEngine, FileIO


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
        """生成 AGENTS.md 内容（保留原有功能）"""
        lines = [self.template_content]

        if include_crystals:
            crystals = self.engine.parse_crystals()
            if crystals:
                lines.append("\n## 核心晶体卡片（认知资源）\n")
                lines.append("| ID | 内容摘要 | 链接 |")
                lines.append("|----|---------|------|")
                for c in crystals[:max_crystals]:
                    content = c.content[:60] + ("..." if len(c.content) > 60 else "")
                    links = ", ".join(c.links[:3]) + ("..." if len(c.links) > 3 else "")
                    lines.append(f"| {c.id} | {content} | {links or '—'} |")
                if len(crystals) > max_crystals:
                    lines.append(f"\n*（共 {len(crystals)} 条晶体，仅显示前 {max_crystals} 条）*")

        lines.append(f"\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append(f"*数据根目录：{Config.DATA_ROOT}*")
        return "\n".join(lines)

    def export_skill_directory(self, crystal_id: str, output_dir: Path) -> Dict[str, str]:
        """导出单个 Skill 目录（保留原有功能）"""
        crystals = self.engine.parse_crystals()
        crystal = next((c for c in crystals if c.id == crystal_id), None)
        if not crystal:
            return {"error": f"未找到晶体 {crystal_id}"}

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        result = {}

        # CRYSTAL.md
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

        # validate.py（简略版）
        validate_py_path = output_dir / "validate.py"
        validate_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证脚本骨架"""
import sys

def validate(content: str) -> dict:
    checks = {
        "has_content": bool(content and content.strip()),
        "length_ok": 10 <= len(content) <= 500,
        "has_links": bool(re.search(r'C\\d{3}|H\\d{3}', content)) if __import__('re') else False,
    }
    score = sum(1 for v in checks.values() if v) / len(checks)
    return {"valid": score >= 0.75, "checks": checks, "score": round(score, 2)}
'''
        validate_py_path.write_text(validate_content, encoding="utf-8")
        result["validate.py"] = str(validate_py_path)

        # references/
        refs_dir = output_dir / "references"
        refs_dir.mkdir(exist_ok=True)
        if crystal.links:
            for i, link in enumerate(crystal.links[:5]):
                (refs_dir / f"ref_{i+1}.md").write_text(f"# 引用 {i+1}\n\n来源：{link}", encoding="utf-8")
        else:
            (refs_dir / "README.md").write_text("# 引用目录\n\n暂无外部引用", encoding="utf-8")
        result["references/"] = str(refs_dir)

        return result

    def export_all_skills(self, output_dir: Path, max_skills: int = 10) -> Dict[str, Any]:
        """导出所有 Skill（保留）"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        crystals = self.engine.parse_crystals()
        results = {"total": len(crystals), "exported": 0, "failed": 0, "details": []}
        for c in crystals[:max_skills]:
            skill_dir = output_dir / f"skill_{c.id}"
            try:
                res = self.export_skill_directory(c.id, skill_dir)
                if "error" in res:
                    results["failed"] += 1
                    results["details"].append({"id": c.id, "status": "failed", "error": res["error"]})
                else:
                    results["exported"] += 1
                    results["details"].append({"id": c.id, "status": "success", "files": list(res.keys())})
            except Exception as e:
                results["failed"] += 1
                results["details"].append({"id": c.id, "status": "failed", "error": str(e)})
        (output_dir / "AGENTS.md").write_text(self.generate_agents_md(), encoding="utf-8")
        results["agents_md"] = str(output_dir / "AGENTS.md")
        return results


# ===== 全局辅助函数（供 GUI/API 调用）=====

def export_agents_md(engine: Optional[CrystalEngine] = None) -> str:
    """生成 AGENTS.md 内容"""
    exporter = AgentsExporter(engine)
    return exporter.generate_agents_md()


def export_skill(crystal_id: str, output_dir: str, engine: Optional[CrystalEngine] = None) -> Dict[str, str]:
    """导出单个 Skill"""
    exporter = AgentsExporter(engine)
    return exporter.export_skill_directory(crystal_id, Path(output_dir))


# ===== Day 19 新增：导出 .github/cognitive-tree/ 目录 =====

def _build_rules_json(engine: Optional['CrystalEngine']) -> Dict[str, Any]:
    """构建 rules.json"""
    rules = {
        "defense_lines": {
            "knowledge_poverty": {"threshold": 0.5, "description": "晶体引用率低于50%触发"},
            "bias_inflation": {"threshold": 0.3, "description": "偏见强化指数超过0.3触发"},
            "information_starvation": {"threshold": 3, "description": "连续3轮无新外部数据触发"},
            "thought_stagnation": {"threshold": 0.8, "consecutive": 3, "description": "连续3轮Jaccard>0.8触发"}
        },
        "meta_primitives": {},
        "layer_rules": {"L1_max": 47, "L2_to_L3_heat": 0.1, "L2_to_L3_days": 30}
    }
    # 从 Config 读取实际值
    try:
        rules["defense_lines"]["knowledge_poverty"]["threshold"] = Config.ALARM_RULES.get("knowledge_poverty", {}).get("threshold", 0.5)
        rules["defense_lines"]["bias_inflation"]["threshold"] = Config.ALARM_RULES.get("bias_inflation", {}).get("threshold", 0.3)
        if hasattr(Config, "L1_MAX"):
            rules["layer_rules"]["L1_max"] = Config.L1_MAX
    except:
        pass
    return rules


def _export_skills(skills_dir: Path, engine: Optional['CrystalEngine'], max_skills: int = 1000):
    """
    导出 skills/ 目录，复制现有Skill或生成骨架

    Args:
        skills_dir: 目标目录
        engine: CrystalEngine 实例
        max_skills: 最大导出数量，默认1000（即全部）
    """
    if engine is None:
        return
    all_skills = engine.get_all_skills() if hasattr(engine, 'get_all_skills') else []
    # 如果 max_skills 为 0 或负数，导出全部
    limit = len(all_skills) if max_skills <= 0 else min(len(all_skills), max_skills)
    for skill_id in all_skills[:limit]:
        src = engine.get_skill_path(skill_id) if hasattr(engine, 'get_skill_path') else None
        if src and src.exists():
            dst = skills_dir / skill_id
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            # 生成骨架
            (skills_dir / skill_id).mkdir(exist_ok=True)
            (skills_dir / skill_id / "CRYSTAL.md").write_text(
                f"# {skill_id}\n\n待补充", encoding="utf-8"
            )
            (skills_dir / skill_id / "validate.py").write_text(
                "#!/usr/bin/env python3\n# 验证脚本\npass", encoding="utf-8"
            )
            (skills_dir / skill_id / "references").mkdir(exist_ok=True)


def _export_prompts(prompts_dir: Path, engine: Optional['CrystalEngine']):
    """导出 prompts/ 目录"""
    role_file = Config.get_path("roles") if hasattr(Config, 'get_path') else None
    if role_file and role_file.exists():
        shutil.copy(role_file, prompts_dir / "roles.json")
    else:
        default_roles = {
            "radical": {"name": "激进者", "instruction": "攻击默认前提..."},
            "conservative": {"name": "保守者", "instruction": "风险优先..."}
        }
        (prompts_dir / "roles.json").write_text(
            json.dumps(default_roles, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    template_file = Config.DATA_ROOT / "核心配置" / "辩论角色模板.json"
    if template_file.exists():
        shutil.copy(template_file, prompts_dir / "辩论角色模板.json")


def _build_readme_comparison() -> str:
    """生成 README.md 对比表"""
    return """# 认知晶体树 - 开源版 vs 云版对比

| 功能 | 开源版（免费） | 云版/App（付费） |
|------|---------------|-----------------|
| 核心认知引擎 | ✅ | ✅ |
| 多角色辩论 | ✅ | ✅ |
| 沉思式反思 | ✅ | ✅ |
| 八道防线 | ✅ | ✅ |
| 自我修复 | ✅（自搭） | ✅（自动） |
| 认知指纹 | ✅（本地） | ✅（云端同步） |
| 跨设备同步 | ❌ | ✅ |
| 云端进化日志 | ❌ | ✅ |
| 高级Skill市场 | ❌ | ✅ |
| 专属技术支持 | ❌ | ✅ |
| 付费Skill分成 | ❌ | ✅ |

**开源版适合**：个人开发者、学习研究、自托管爱好者  
**云版适合**：团队协作、企业用户、希望数据永不丢失的用户

立即体验云版：https://your-cloud-domain.com
"""


def export_github_cognitive_tree(output_dir: str, engine: Optional['CrystalEngine'] = None, max_skills: int = 1000) -> str:
    """
    导出 .github/cognitive-tree/ 目录（Day 19 核心功能）

    Args:
        output_dir: 输出根目录
        engine: CrystalEngine 实例
        max_skills: 最大导出 Skill 数量（默认1000即全部）

    Returns:
        生成的 .github/cognitive-tree/ 目录路径
    """
    output_path = Path(output_dir)
    github_dir = output_path / ".github" / "cognitive-tree"
    github_dir.mkdir(parents=True, exist_ok=True)

    # 1. rules.json
    rules = _build_rules_json(engine)
    with open(github_dir / "rules.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    # 2. skills/
    skills_dir = github_dir / "skills"
    skills_dir.mkdir(exist_ok=True)
    _export_skills(skills_dir, engine, max_skills)   # <--- 传入 max_skills

    # 3. prompts/
    prompts_dir = github_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    _export_prompts(prompts_dir, engine)

    # 4. README.md
    readme_content = _build_readme_comparison()
    with open(github_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    return str(github_dir)