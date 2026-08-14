"""作文因材施教 MVP：五版差异化反馈。"""

from __future__ import annotations

from typing import Any, Dict, List

from .prompts import PROMPTS


VERSION_KEYS = ["学生版", "家长版", "老师版", "专家版", "成长版"]
_KEY_MAP = {
    "student_version": "学生版",
    "parent_version": "家长版",
    "teacher_version": "老师版",
    "expert_version": "专家版",
    "growth_version": "成长版",
}


def build_review_prompt(essay: str, students: List[Dict]) -> str:
    """构建作文五版反馈 Prompt。"""
    profiles = "\n".join(
        f"- {item.get('name', '学生')}：{item.get('profile', '')}"
        for item in (students or [])
    )
    version_requirements = "\n".join(
        f"- {key}：{PROMPTS['report_versions'].get(key, '')}"
        for key in VERSION_KEYS
    )
    return f"""你是「作文因材施教」引擎。请基于同一篇作文，面向以下学生画像，分别输出五版差异化教学反馈。

【学生画像】
{profiles or "（未提供画像，按通用水平分层）"}

【作文原文】
{essay}

【五版要求】
{version_requirements}

【硬性约束】
- 只引用作文原文中的事实，禁止无据断言；
- 不贴“差生/天才”标签，不承诺分数；
- 每版必须给出“当前卡点 / 最大亮点 / 下一步只做一件事”。

只返回 JSON，不要 Markdown 代码块：
{{
  "student_version": "学生版内容",
  "parent_version": "家长版内容",
  "teacher_version": "老师版内容",
  "expert_version": "专家版内容",
  "growth_version": "成长版内容"
}}
"""


def normalize_review(result: Any) -> Dict[str, Any]:
    """把 AI 返回整理为五版结构，缺失项兜底为待补充。"""
    versions: Dict[str, str] = {}
    missing: List[str] = []
    data = result if isinstance(result, dict) else {}
    for key, label in _KEY_MAP.items():
        text = str(data.get(key) or "").strip()
        if not text and isinstance(data.get(label), str):
            text = data[label].strip()
        if text:
            versions[label] = text
        else:
            missing.append(label)
            versions[label] = f"（{label}待补充）"
    return {
        "versions": versions,
        "missing": missing,
        "ok": not missing,
        "evidence_rule": "只引用作文原文中的事实，禁止无据断言",
    }


def review_essay(essay: str, students: List[Dict], ai_client) -> Dict[str, Any]:
    """执行作文五版反馈 MVP：AI 生成 + 归一化 + 缺失兜底。"""
    if not essay or not essay.strip():
        return {"ok": False, "error": "作文内容为空", "versions": {}}
    prompt = build_review_prompt(essay, students)
    try:
        result = ai_client.chat_json(prompt, temperature=0.4)
    except Exception as e:
        result = {"error": str(e)}
    if isinstance(result, dict) and result.get("error"):
        return {"ok": False, "error": result["error"], "versions": {}}
    normalized = normalize_review(result)
    normalized["essay"] = essay[:200]
    return normalized
