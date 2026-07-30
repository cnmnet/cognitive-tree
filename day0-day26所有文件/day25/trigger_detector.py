#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唤醒词检测器（触发词 + 语境绑定）
支持创作者为 Skill 设置专属唤醒词，也支持从晶体核心内容自动提取关键词
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class TriggerRule:
    skill_id: str
    wake_words: List[str]          # 唤醒词列表
    context_patterns: List[str]    # 语境正则
    priority: int = 0              # 优先级

class TriggerDetector:
    def __init__(self, skills_dir: str = "晶体树文件夹/skills"):
        self.skills_dir = Path(skills_dir)
        self.rules: Dict[str, TriggerRule] = {}
        self._load_rules()

    def _load_rules(self):
        """从 skills/*/CRYSTAL.md 读取触发规则，若没有唤醒词则从核心内容提取关键词"""
        if not self.skills_dir.exists():
            print(f"⚠️ 目录不存在: {self.skills_dir}")
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            crystal_md = skill_dir / "CRYSTAL.md"
            if not crystal_md.exists():
                continue
            content = crystal_md.read_text(encoding='utf-8')

            # 1. 尝试提取显式唤醒词
            wake_match = re.search(r"## 唤醒词\s*[:：]\s*(.+)", content)
            if wake_match:
                words = [w.strip() for w in wake_match.group(1).split(",")]
            else:
                words = []

            # 2. 尝试提取显式语境绑定
            context_match = re.search(r"## 语境绑定\s*[:：]\s*(.+)", content)
            if context_match:
                patterns = [p.strip() for p in context_match.group(1).split(",")]
            else:
                patterns = []

            # 3. 如果没有显式唤醒词，从核心内容中自动提取关键词
            if not words:
                core_match = re.search(r"## 核心内容\s*\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
                if core_match:
                    core_text = core_match.group(1).strip()
                    # 提取所有中文字符组合（长度≥2）
                    keywords = re.findall(r'[\u4e00-\u9fff]{2,}', core_text)
                    # 过滤常见停用词
                    stopwords = {"的","了","是","和","与","等","在","有","个","中","上","下","为","对","于","之","其","以","也","就","到","说","要","会","可","以","之","而","所","这","那","不","也","都","从","把","被","让","给","去","来","看","想","做","好","能","得","很","太","更","最","些","后","前","内","外","时","间","年","月","日","次","点","面"}
                    seen = set()
                    for w in keywords:
                        if w not in stopwords and w not in seen and len(w) >= 2:
                            words.append(w)
                            seen.add(w)
                        if len(words) >= 6:  # 最多取6个关键词
                            break

            # 4. 如果仍然没有关键词，使用 Skill ID 本身
            if not words:
                words = [skill_dir.name]  # 如 "C001"

            # 5. 构建规则
            if words or patterns:
                self.rules[skill_dir.name] = TriggerRule(
                    skill_id=skill_dir.name,
                    wake_words=words,
                    context_patterns=patterns,
                    priority=len(words) * 2 + len(patterns)
                )

    def detect(self, user_input: str) -> List[str]:
        """
        根据输入检测应激活的 Skill ID 列表
        返回按优先级排序的 skill_id 列表
        """
        activated = []
        for sid, rule in self.rules.items():
            # 唤醒词匹配（部分匹配即可）
            if rule.wake_words:
                for word in rule.wake_words:
                    if word in user_input:
                        activated.append(sid)
                        break
            # 语境匹配（正则）
            if rule.context_patterns and sid not in activated:
                for pattern in rule.context_patterns:
                    if re.search(pattern, user_input):
                        activated.append(sid)
                        break
        # 按优先级排序
        activated.sort(key=lambda x: self.rules[x].priority, reverse=True)
        return activated

if __name__ == "__main__":
    # 自测入口
    detector = TriggerDetector()
    test_inputs = [
        "帮我做一个反脆弱决策分析",
        "这项目风险太高了，怎么控制？",
        "我需要评估注意力质量",          # 包含“注意力质量”
        "今天天气不错"
    ]
    print("🔍 触发检测测试")
    print("-" * 40)
    for text in test_inputs:
        result = detector.detect(text)
        print(f"输入: {text}")
        print(f"激活: {result if result else '（无激活）'}")
        print()