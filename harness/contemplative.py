#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from external.ai_client import AIClient
from harness.engine import CrystalEngine

class ContemplativeEngine:
    """
    沉思式反思引擎

    为AI增加四个维度指令：
    - 正念 (Mindfulness): 自我监控与校准
    - 空性 (Emptiness): 防止僵化目标
    - 非二元性 (Non-duality): 消融对立边界
    - 无边关怀 (Boundless Care): 普世关怀

    论文依据: 《Contemplative Wisdom for Superalignment》(普林斯顿大学, 2026)
    """

    def __init__(self, ai_client: 'AIClient', engine: 'CrystalEngine'):
        self.ai = ai_client
        self.engine = engine
        self.reflection_history: List[Dict] = []

    def reflect(self, question: str, debate_rounds: List[Dict]) -> Dict[str, Any]:
        """
        执行沉思式反思。

        基于正念、空性、非二元性、无边关怀四个维度进行深度反思。

        Args:
            question (str): 原始问题
            debate_rounds (List[Dict]): 辩论轮次数据列表

        Returns:
            dict: 包含以下四个维度的反思结果
                - mindfulness (str): 正念观察
                - emptiness (str): 空性洞察
                - non_duality (str): 非二元性整合
                - boundless_care (str): 无边关怀
                - wise_echo (str): 智慧回响（综合输出）
        """
        # 提取辩论摘要
        summary = self._extract_debate_summary(debate_rounds)

        # 四个维度的反思
        mindfulness = self._mindfulness_reflection(question, summary)
        emptiness = self._emptiness_reflection(question, summary)
        non_duality = self._non_duality_reflection(question, summary)
        boundless_care = self._boundless_care_reflection(question, summary)

        # 生成智慧回响
        wise_echo = self._generate_wise_echo(
            question, summary,
            mindfulness, emptiness, non_duality, boundless_care
        )

        result = {
            "mindfulness": mindfulness,
            "emptiness": emptiness,
            "non_duality": non_duality,
            "boundless_care": boundless_care,
            "wise_echo": wise_echo,
            "trigger": "contemplative_reflection"
        }

        self.reflection_history.append(result)
        return result

    def _extract_debate_summary(self, debate_rounds: List[Dict]) -> str:
        """提取辩论摘要"""
        if not debate_rounds:
            return "（无辩论数据）"

        # 获取最后一轮的审计摘要
        last_round = debate_rounds[-1]
        audit = last_round.get("audit", {})
        summary = audit.get("summary", "")

        # 如果审计摘要为空，从答案中提取
        if not summary:
            answers = last_round.get("answers", [])
            for ans in answers[:3]:
                if ans.get("role") == "大法官":
                    summary = ans.get("answer", "")[:200]
                    break
            if not summary:
                summary = "辩论产生了一系列观点，但未形成明确摘要。"

        return summary

    def _mindfulness_reflection(self, question: str, summary: str) -> str:
        """
        正念：自我监控与校准
        观察辩论过程中的认知偏差、情绪波动、思维定式
        """
        prompt = f"""
请以「正念」的视角，对以下辩论进行观察性反思。

【问题】
{question}

【辩论摘要】
{summary}

【正念反思要求】
1. 观察这场辩论中出现了哪些「认知偏差」？（如确认偏误、锚定效应）
2. 辩论过程中，哪些观点被过度强化，哪些被忽视？
3. 是否有「思维定式」在主导讨论走向？

【输出格式】
200字以内，以"正念观察："开头，用平实、中性的语言描述。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.5)
            return result.strip() if result else "（正念观察生成中）"
        except:
            return "（正念观察生成中）"

    def _emptiness_reflection(self, question: str, summary: str) -> str:
        """
        空性：防止僵化目标
        质疑问题的假设前提，看到"空"的可能性
        """
        prompt = f"""
请以「空性」的视角，对以下问题进行深度反思。

【问题】
{question}

【辩论摘要】
{summary}

【空性反思要求】
1. 这个问题本身的「假设前提」是什么？这些假设是否可靠？
2. 是否存在「问题之外的问题」——即真正需要被关注的更底层议题？
3. 如果完全放下当前的目标框架，会看到什么新的可能性？

【输出格式】
200字以内，以"空性洞察："开头，语言要有通透感。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.6)
            return result.strip() if result else "（空性洞察生成中）"
        except:
            return "（空性洞察生成中）"

    def _non_duality_reflection(self, question: str, summary: str) -> str:
        """
        非二元性：消融对立边界
        看到A/B、对/错、输/赢之外的第三空间
        """
        prompt = f"""
请以「非二元性」的视角，对以下辩论进行整合性反思。

【问题】
{question}

【辩论摘要】
{summary}

【非二元性反思要求】
1. 这场辩论中出现了哪些「二元对立」？（如A vs B、对 vs 错）
2. 这些对立背后，是否有一个「第三空间」——即超越对立的更高维度？
3. 如果消融这些边界，会看到什么样的整合方案？

【输出格式】
200字以内，以"非二元性整合："开头，语言要有包容感。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.7)
            return result.strip() if result else "（非二元性整合生成中）"
        except:
            return "（非二元性整合生成中）"

    def _boundless_care_reflection(self, question: str, summary: str) -> str:
        """
        无边关怀：普世关怀
        将决策与更广泛的人类福祉、生态、未来联系起来
        """
        prompt = f"""
请以「无边关怀」的视角，对以下辩论进行价值反思。

【问题】
{question}

【辩论摘要】
{summary}

【无边关怀反思要求】
1. 这个决策或问题，与「更多人」有什么关联？
2. 除了直接利益相关者，还有谁会被影响？
3. 从长远来看（10年、100年），这个决策意味着什么？

【输出格式】
200字以内，以"无边关怀："开头，语言要有温暖感和开阔感。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.6)
            return result.strip() if result else "（无边关怀生成中）"
        except:
            return "（无边关怀生成中）"

    def _generate_wise_echo(self, question: str, summary: str,
                            mindfulness: str, emptiness: str,
                            non_duality: str, boundless_care: str) -> str:
        """
        生成智慧回响：整合四个维度的综合输出
        包含中国传统文化意象
        """
        prompt = f"""
请综合以下四个维度的反思，生成一段「智慧回响」。

【问题】
{question}

【辩论摘要】
{summary}

【四维度反思】
正念观察：{mindfulness}
空性洞察：{emptiness}
非二元性整合：{non_duality}
无边关怀：{boundless_care}

【智慧回响要求】
1. 融合四个维度的精髓，形成一个完整的"智慧回响"
2. 自然融入中国传统文化意象（如山水、明月、竹、云等）
3. 语言风格：从容、通透、有温度
4. 引用或化用一句古诗词或经典（如"如切如磋，如琢如磨"）
5. 字数：150-250字

【输出格式】
直接输出正文，不加标题、不加序号。
"""
        try:
            result = self.ai.chat(prompt, temperature=0.7)
            if result and len(result) > 50:
                return result.strip()
        except:
            pass

        # 降级方案
        return f"""以我观之，此事如月映千江，各有其明。正念所照，见心之波澜；空性所示，破执之牢笼；非二元所融，消对立之边界；无边关怀所及，通万物之灵犀。

如竹之虚心，如水的随形，如山的厚重，如云的轻盈——此四者相济，方成智慧之回响。

{summary[:80]}。

{question[:50]}，行于道中，自有答案。如切如磋，如琢如磨，此之谓也。"""

