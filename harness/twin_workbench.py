#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from external.ai_client import AIClient
from governance.config import Config
from harness.engine import CrystalEngine

@dataclass
class TwinProfile:
    """替身认知指纹"""
    name: str
    role: str  # "决策替身" | "学习替身" | "社交替身"
    fingerprint: Dict[str, Any] = field(default_factory=dict)
    history: List[Tuple[str, str]] = field(default_factory=list)
    crystals: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())

# =============================================================================
# Day 13.5: 沉思式反思引擎 (ContemplativeEngine)
# =============================================================================

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

class TwinWorkbench:
    """
    多替身并行工作台
    
    用户可创建3个独立替身：
    - 决策替身：用于复杂决策问题
    - 学习替身：用于知识获取和整理
    - 社交替身：用于人际沟通和表达
    
    每个替身独立积累认知指纹和晶体，定期由"结构主义者"进行跨替身整合。
    """
    
    def __init__(self, engine: 'CrystalEngine', ai_client: 'AIClient'):
        self.engine = engine
        self.ai = ai_client
        self.twins: Dict[str, TwinProfile] = {}
        self._load_twins()
    
    def _load_twins(self):
        """从文件加载替身数据"""
        twin_path = Config.DATA_ROOT / "系统日志" / "twin_profiles.json"
        if twin_path.exists():
            try:
                import json
                with open(twin_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, profile_data in data.items():
                        self.twins[name] = TwinProfile(
                            name=profile_data.get("name", name),
                            role=profile_data.get("role", "未知"),
                            fingerprint=profile_data.get("fingerprint", {}),
                            history=profile_data.get("history", []),
                            crystals=profile_data.get("crystals", []),
                            created_at=profile_data.get("created_at", datetime.now().isoformat()),
                            last_active=profile_data.get("last_active", datetime.now().isoformat())
                        )
            except Exception as e:
                print(f"⚠️ 加载替身数据失败: {e}")
    
    def _save_twins(self):
        """保存替身数据到文件"""
        twin_path = Config.DATA_ROOT / "系统日志" / "twin_profiles.json"
        twin_path.parent.mkdir(parents=True, exist_ok=True)
        import json
        data = {}
        for name, twin in self.twins.items():
            data[name] = {
                "name": twin.name,
                "role": twin.role,
                "fingerprint": twin.fingerprint,
                "history": twin.history,
                "crystals": twin.crystals,
                "created_at": twin.created_at,
                "last_active": twin.last_active
            }
        with open(twin_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create_twin(self, name: str, role: str) -> TwinProfile:
        """创建一个新的替身"""
        if name in self.twins:
            return self.twins[name]
        
        # 根据角色生成初始指纹
        initial_fingerprint = self._generate_initial_fingerprint(role)
        
        twin = TwinProfile(
            name=name,
            role=role,
            fingerprint=initial_fingerprint
        )
        self.twins[name] = twin
        self._save_twins()
        return twin
    
    def _generate_initial_fingerprint(self, role: str) -> Dict[str, Any]:
        """根据角色生成初始指纹"""
        fingerprints = {
            "决策替身": {
                "risk_tolerance": 0.7,
                "innovation_preference": 0.8,
                "decisiveness": 0.9,
                "attention_span": 0.7,
                "preferred_role": "radical",
                "reasoning_style": "deductive",
                "analogy_preference": "first_principles",
                "output_style": "conclusion_first",
                "confidence": 0.5,
                "total_interactions": 0
            },
            "学习替身": {
                "risk_tolerance": 0.3,
                "innovation_preference": 0.5,
                "decisiveness": 0.4,
                "attention_span": 0.9,
                "preferred_role": "structural",
                "reasoning_style": "inductive",
                "analogy_preference": "analogy",
                "output_style": "evidence_first",
                "confidence": 0.5,
                "total_interactions": 0
            },
            "社交替身": {
                "risk_tolerance": 0.5,
                "innovation_preference": 0.6,
                "decisiveness": 0.5,
                "attention_span": 0.6,
                "preferred_role": "spokesperson",
                "reasoning_style": "balanced",
                "analogy_preference": "balanced",
                "output_style": "balanced",
                "confidence": 0.5,
                "total_interactions": 0
            }
        }
        return fingerprints.get(role, fingerprints["学习替身"])
    
    def get_twin(self, name: str) -> Optional[TwinProfile]:
        """获取替身"""
        return self.twins.get(name)
    
    def get_all_twins(self) -> Dict[str, TwinProfile]:
        """获取所有替身"""
        return self.twins
    
    def chat_with_twin(self, twin_name: str, message: str) -> str:
        """与指定替身对话"""
        twin = self.get_twin(twin_name)
        if not twin:
            return f"❌ 替身 {twin_name} 不存在"

        # 构建替身专属的 System Prompt
        system = f"""你是认知晶体树中的【{twin.role}】。

你的角色特征：
- 决策风格：{self._describe_fingerprint(twin.fingerprint)}
- 核心使命：{self._describe_role_mission(twin.role)}

请以这个身份回答问题，保持角色一致性。
"""

        # 记录用户消息到历史
        twin.history.append(("user", message))

        # 调用 AI（使用完整历史）
        if len(twin.history) > 0:
            reply = self.ai.chat_with_history(twin.history, system=system)
        else:
            reply = self.ai.chat(message, system=system)

        # 记录 AI 回复到历史
        twin.history.append(("assistant", reply))
        twin.last_active = datetime.now().isoformat()

        # 更新指纹
        twin.fingerprint["total_interactions"] = twin.fingerprint.get("total_interactions", 0) + 1
        twin.fingerprint["confidence"] = min(0.9, 0.3 + twin.fingerprint["total_interactions"] * 0.02)

        # 保存到文件
        self._save_twins()

        return reply
    
    def _describe_fingerprint(self, fp: Dict) -> str:
        """描述指纹特征"""
        risk = "高风险高回报" if fp.get("risk_tolerance", 0.5) > 0.6 else "低风险稳健"
        decision = "快速决断" if fp.get("decisiveness", 0.5) > 0.6 else "深思熟虑"
        return f"{risk}，{decision}"
    
    def _describe_role_mission(self, role: str) -> str:
        """描述角色使命"""
        missions = {
            "决策替身": "在复杂决策中提供清晰的判断和行动建议",
            "学习替身": "系统性地整理和消化新知识，构建知识体系",
            "社交替身": "在人际沟通和表达中保持真诚和温度"
        }
        return missions.get(role, "提供有价值的见解")
    
    def integrate_twins(self) -> Dict[str, Any]:
        """
        跨替身整合：由"结构主义者"整合三个替身的认知
        """
        # 重新加载数据，确保是最新的
        self._load_twins()

        if len(self.twins) < 2:
            return {"error": "至少需要2个替身才能整合"}

        # 检查每个替身是否有对话记录
        has_history = False
        twin_summaries = []
        for name, twin in self.twins.items():
            if twin.history and len(twin.history) >= 2:  # 至少有一轮完整对话
                has_history = True
                # 取最近6条对话作为摘要
                recent = twin.history[-6:] if len(twin.history) >= 6 else twin.history
                summary = ""
                for role, content in recent:
                    label = "用户" if role == "user" else f"{name}"
                    summary += f"{label}: {content[:100]}...\n"
                twin_summaries.append(f"【{name}】（{twin.role}）\n{summary}")

        if not has_history:
            return {"error": "替身尚无对话记录，请先与替身对话"}

        prompt = f"""
你是认知晶体树中的【结构主义者】。

请整合以下三个替身的观点，找出共性、差异和互补点：

{chr(10).join(twin_summaries)}

【输出要求】
只返回 JSON，格式：
{{
    "common_ground": "三个替身的共同认知",
    "differences": "主要分歧点",
    "synergy": "互补价值（如何结合使用）",
    "integrated_insight": "整合后的核心洞察（100字内）"
}}
"""
        try:
            result = self.ai.chat_json(prompt, temperature=0.5)
            if "error" in result:
                return {"error": f"AI 解析失败: {result.get('error', '')}"}
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def get_twin_status(self) -> Dict[str, Any]:
        """获取替身状态"""
        status = {}
        for name, twin in self.twins.items():
            status[name] = {
                "role": twin.role,
                "interactions": len(twin.history),
                "crystals": len(twin.crystals),
                "confidence": twin.fingerprint.get("confidence", 0.3),
                "last_active": twin.last_active,
                "created_at": twin.created_at
            }
        return status

# ===== Day 25: GitHub Skill 市场集成 =====

