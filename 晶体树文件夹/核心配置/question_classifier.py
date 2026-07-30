# -*- coding: utf-8 -*-
"""
元问题分类器 (纯规则，零LLM成本)
路径：晶体树文件夹/核心配置/question_classifier.py
"""

import re
from typing import Dict, Tuple

class QuestionClassifier:
    """基于规则的问题分类器"""

    # 类型映射
    TYPE_FACT = "fact_query"
    TYPE_DECISION = "decision_dilemma"
    TYPE_CREATIVE = "creative_inspiration"
    TYPE_REFLECTIVE = "reflective_deepening"
    TYPE_UNKNOWN = "unknown"

    # 规则模式
    PATTERNS = {
        TYPE_FACT: [
            r"什么是\s*(.+?)[？?]?$",
            r"(.+?)\s*是什么[？?]?$",
            r"请解释\s*(.+?)[？?]?$",
            r"说说\s*(.+?)\s*的定义",
        ],
        TYPE_DECISION: [
            r"我应该选\s*(.+?)\s*还是\s*(.+?)[？?]?$",
            r"(.+?)\s*还是\s*(.+?)[？?]?$",
            r"选择\s*(.+?)\s*还是\s*(.+?)[？?]?$",
            r"选\s*(.+?)\s*还是\s*(.+?)[？?]?$",
            r"决策[:：]\s*(.+)",
        ],
        TYPE_CREATIVE: [
            r"给我一些\s*(.+?)\s*想法",
            r"有哪些\s*(.+?)\s*创意",    # ← 新增
            r"有哪些\s*(.+?)\s*方法",    # ← 新增
            r"有哪些\s*(.+?)\s*创意",
            r"请提供\s*(.+?)\s*建议",
            r" brainstorm\s*(.+)",
            r"创意[:：]\s*(.+)",
        ],
        TYPE_REFLECTIVE: [
            r"我这样想对吗[？?]?$",
            r"这样想对不对[？?]?$",
            r"我的\s*(.+?)\s*想法正确吗",
            r"是否\s*合理",              # ← 新增
            r"反思[:：]\s*(.+)",
            r"我\s*(.+?)\s*这样判断对吗",
        ],
    }

    def __init__(self):
        # 编译正则表达式
        self.compiled_patterns = {}
        for qtype, patterns in self.PATTERNS.items():
            self.compiled_patterns[qtype] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def classify(self, question: str) -> Dict[str, str]:
        """
        分类问题，返回 { "type": str, "path": str, "label": str }
        """
        question = question.strip()
        if not question:
            return {"type": self.TYPE_UNKNOWN, "path": "unknown", "label": "未知问题"}

        # 1. 长度过短 → 简单问候，归为未知
        if len(question) < 4:
            return {"type": self.TYPE_UNKNOWN, "path": "rule_engine", "label": "简短问候/确认"}

        # 2. 遍历模式匹配
        for qtype, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(question):
                    label_map = {
                        self.TYPE_FACT: "事实查询",
                        self.TYPE_DECISION: "决策困境",
                        self.TYPE_CREATIVE: "创意启发",
                        self.TYPE_REFLECTIVE: "反思深化",
                    }
                    path_map = {
                        self.TYPE_FACT: "fast_retrieval",
                        self.TYPE_DECISION: "debate_voting",
                        self.TYPE_CREATIVE: "lark_association",
                        self.TYPE_REFLECTIVE: "contemplative_reflection",
                    }
                    return {
                        "type": qtype,
                        "path": path_map[qtype],
                        "label": label_map[qtype]
                    }

        # 新增：简短问候/闲聊检测（长度 ≤ 8 且含"怎么样"）→ 归为 unknown
        if len(question) <= 8 and "怎么样" in question:
            return {"type": self.TYPE_UNKNOWN, "path": "rule_engine", "label": "简短问候/闲聊"}

        # 3. 关键词兜底（未命中模式但含关键词）
        if any(kw in question for kw in ["如何", "怎样", "怎么"]):
            return {"type": self.TYPE_FACT, "path": "fast_retrieval", "label": "方法查询（归为事实类）"}
        if any(kw in question for kw in ["选择", "比较", "利弊"]):
            return {"type": self.TYPE_DECISION, "path": "debate_voting", "label": "权衡比较（归为决策类）"}
        if any(kw in question for kw in ["想法", "创意", "建议", "方案", "方法", "方式", "途径"]):
            return {"type": self.TYPE_CREATIVE, "path": "lark_association", "label": "创意生成（归为创意类）"}
        if any(kw in question for kw in ["对", "错", "正确", "反思", "合理", "合乎逻辑"]):
            return {"type": self.TYPE_REFLECTIVE, "path": "contemplative_reflection", "label": "自我检验（归为反思类）"}

        # 4. 默认：未知，使用通用路径
        return {"type": self.TYPE_UNKNOWN, "path": "general", "label": "一般问题"}

    def get_route_description(self, classification: Dict) -> str:
        """生成可读的路由描述"""
        label = classification.get("label", "未知")
        path = classification.get("path", "general")
        desc_map = {
            "fast_retrieval": "走快速检索路径（晶体检索+简短回答）",
            "debate_voting": "走辩论+投票路径（启动多角色辩论引擎）",
            "lark_association": "走百灵鸟+联想路径（开放联想+外部知识）",
            "contemplative_reflection": "走沉思式反思路径（触发四维度沉思）",
            "rule_engine": "走规则引擎直接回答",
            "general": "走通用AI对话",
        }
        desc = desc_map.get(path, "走通用AI对话")
        return f"当前问题被分类为：{label}，{desc}"