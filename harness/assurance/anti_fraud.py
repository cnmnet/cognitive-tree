#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

class AIPersonaDetector:
    """
    AI人设检测器

    输入一段对话，判断对方是否为AI驱动的多角色伪装
    基于：发言模式、响应速度、语义连贯性异常
    """

    def __init__(self):
        self.suspicious_patterns = [
            r"我是.*助手",
            r"作为一名.*AI",
            r"我的训练数据",
            r"我没有.*感情",
            r"我只是.*程序",
        ]

    def detect(self, dialogue: str) -> Dict[str, Any]:
        """
        检测对话中的AI人设伪装

        Args:
            dialogue: 对话文本

        Returns:
            Dict:
                - passed: bool 是否通过（无伪装）
                - risk_level: str "low" | "medium" | "high"
                - records: List 检测记录
                - reason: str
        """
        import re

        if not dialogue or len(dialogue) < 10:
            return {"passed": True, "risk_level": "low", "records": [], "reason": "对话过短，无法判断"}

        records = []
        risk_score = 0

        # 1. 检测AI自曝模式
        for pattern in self.suspicious_patterns:
            matches = re.findall(pattern, dialogue, re.IGNORECASE)
            if matches:
                records.append({
                    "type": "ai_self_disclosure",
                    "pattern": pattern,
                    "count": len(matches)
                })
                risk_score += len(matches) * 10

        # 2. 检测发言模式异常（过于规整、句式重复）
        sentences = re.split(r'[。！？；\n]', dialogue)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            # 过于均匀的长度可能是AI生成
            if all(len(s) < avg_len * 1.3 and len(s) > avg_len * 0.7 for s in sentences[:5]):
                records.append({
                    "type": "uniform_sentence_length",
                    "avg_length": round(avg_len, 1)
                })
                risk_score += 15

        # 3. 检测语义连贯性异常（前后矛盾或过于跳跃）
        # 简化检测：检查是否有明显的转折词频繁出现
        contrast_words = ["但是", "然而", "不过", "虽然", "尽管"]
        contrast_count = sum(1 for w in contrast_words if w in dialogue)
        if contrast_count > 3:
            records.append({
                "type": "frequent_contrast",
                "contrast_count": contrast_count
            })
            risk_score += 5

        # 4. 检测是否有明确的"人设"陈述
        persona_indicators = ["我的观点是", "我认为", "我倾向于", "我理解", "我感受到"]
        persona_count = sum(1 for w in persona_indicators if w in dialogue)
        if persona_count > 5:
            records.append({
                "type": "excessive_persona_statements",
                "count": persona_count
            })
            risk_score += 10

        # 综合判断
        if risk_score >= 40:
            risk_level = "high"
            passed = False
            reason = f"检测到多个AI人设伪装特征（风险分{risk_score}）"
        elif risk_score >= 20:
            risk_level = "medium"
            passed = True
            reason = f"存在可疑人设特征（风险分{risk_score}），建议人工复核"
        else:
            risk_level = "low"
            passed = True
            reason = "未检测到明显伪装特征"

        return {
            "passed": passed,
            "risk_level": risk_level,
            "records": records,
            "reason": reason,
            "risk_score": risk_score
        }


class StarlinkFingerprintDB:
    """
    星链信号指纹库

    记录已知诈骗园区的网络信号特征
    当系统检测到来自这些IP段的请求时自动标记
    """

    # 已知诈骗园区IP段（示例数据）
    KNOWN_CAMPS = [
        {"name": "缅北地区", "ip_ranges": ["103.23.0.0/16", "103.24.0.0/16"], "risk_level": "high"},
        {"name": "柬埔寨西港", "ip_ranges": ["103.81.0.0/16"], "risk_level": "high"},
        {"name": "菲律宾马尼拉", "ip_ranges": ["103.240.0.0/16"], "risk_level": "medium"},
        {"name": "迪拜", "ip_ranges": ["94.206.0.0/16"], "risk_level": "medium"},
        {"name": "格鲁吉亚", "ip_ranges": ["176.73.0.0/16"], "risk_level": "medium"},
    ]

    def __init__(self):
        self.fingerprint_db = self.KNOWN_CAMPS

    def check(self, ip: str) -> Dict[str, Any]:
        """
        检查IP是否来自已知诈骗园区

        Args:
            ip: IP地址（如 "103.23.1.100"）

        Returns:
            Dict:
                - passed: bool 是否通过（不在黑名单中）
                - matched_camp: str 匹配的园区名称
                - risk_level: str
                - reason: str
        """
        import ipaddress

        if not ip:
            return {"passed": True, "matched_camp": None, "risk_level": "low", "reason": "IP为空"}

        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return {"passed": True, "matched_camp": None, "risk_level": "low", "reason": f"无效IP: {ip}"}

        for camp in self.fingerprint_db:
            for ip_range in camp["ip_ranges"]:
                try:
                    if ip_obj in ipaddress.ip_network(ip_range):
                        return {
                            "passed": False,
                            "matched_camp": camp["name"],
                            "risk_level": camp["risk_level"],
                            "reason": f"IP {ip} 匹配已知诈骗园区: {camp['name']}",
                            "ip_range": ip_range
                        }
                except:
                    continue

        return {
            "passed": True,
            "matched_camp": None,
            "risk_level": "low",
            "reason": f"IP {ip} 未匹配已知诈骗园区"
        }

    def add_camp(self, name: str, ip_ranges: List[str], risk_level: str = "medium") -> None:
        """添加新的园区到指纹库"""
        self.fingerprint_db.append({
            "name": name,
            "ip_ranges": ip_ranges,
            "risk_level": risk_level
        })


class CrossLingualAuditor:
    """
    跨语言语义一致性审计

    检测同一句话在不同语言版本中是否语义一致
    诈骗团伙常用翻译漏洞制造信任
    """

    def __init__(self, ai_client: Any = None):
        self.ai = ai_client

    def audit(self, text_zh: str, text_en: str) -> Dict[str, Any]:
        """
        审计中英文语义一致性

        Args:
            text_zh: 中文文本
            text_en: 英文文本

        Returns:
            Dict:
                - passed: bool 是否语义一致
                - zh_meaning: str 中文核心含义
                - en_meaning: str 英文核心含义
                - overlap_ratio: float 关键词重叠度
                - confidence: float 审计置信度
                - reason: str
                - is_consistent: bool
        """
        if not text_zh or not text_en:
            return {
                "passed": False,
                "reason": "缺少对照文本",
                "confidence": 0.0,
                "overlap_ratio": 0.0,
                "is_consistent": False,
                "zh_meaning": text_zh[:50] if text_zh else "",
                "en_meaning": text_en[:50] if text_en else ""
            }

        # 1. 提取关键词
        zh_keywords = self._extract_keywords(text_zh)
        en_keywords = self._extract_keywords(text_en)

        # ===== 修复点：改进重叠度计算 =====
        # 将中文关键词翻译为英文（简化版：保持原样，但提取核心名词）
        zh_set = set(zh_keywords)
        en_set = set(en_keywords)

        # 计算重叠度时，考虑中英文的语义等价词
        # 例如："知识" ≈ "knowledge", "AI" ≈ "人工智能"
        semantic_map = {
            "知识": "knowledge", "学习": "learn", "理解": "understand",
            "用户": "user", "系统": "system", "认知": "cognitive",
            "晶体": "crystal", "树": "tree", "人工智能": "AI",
            "智能": "intelligent", "模型": "model", "算法": "algorithm"
        }

        # 扩展中文集合：加入语义映射的英文词
        zh_set_extended = set(zh_set)
        for zh_word in zh_set:
            if zh_word in semantic_map:
                zh_set_extended.add(semantic_map[zh_word])

        # 同样扩展英文集合：反向映射
        reverse_map = {v: k for k, v in semantic_map.items()}
        en_set_extended = set(en_set)
        for en_word in en_set:
            if en_word.lower() in reverse_map:
                en_set_extended.add(reverse_map[en_word.lower()])

        # 计算重叠度
        overlap = len(zh_set_extended & en_set_extended) / max(len(zh_set_extended), len(en_set_extended), 1)

        # 2. 提取核心含义
        zh_meaning = self._extract_core_meaning(text_zh)
        en_meaning = self._extract_core_meaning(text_en)

        # 3. 判断是否一致（阈值降低，因为语义映射增加了召回）
        is_consistent = overlap > 0.2

        return {
            "passed": is_consistent,
            "zh_meaning": zh_meaning[:50],
            "en_meaning": en_meaning[:50],
            "overlap_ratio": round(overlap, 2),
            "confidence": min(0.9, 0.4 + overlap * 0.5),
            "reason": "语义一致" if is_consistent else f"关键词重叠度低 ({overlap:.2f})，可能存在语义偏差",
            "is_consistent": is_consistent
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词（优化版）

        改进：
        1. 中文：使用 jieba 分词（如果可用），否则使用字符级提取
        2. 英文：提取词干（简化版）
        3. 过滤停用词
        """
        import re

        # 尝试使用 jieba 分词（更准确）
        try:
            import jieba
            words = jieba.lcut(text)
        except ImportError:
            # 降级方案：正则提取
            # 中文：提取2-4个中文字符的组合
            zh_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
            # 英文：提取3个以上字母的词
            en_words = re.findall(r'[A-Za-z]{3,}', text)
            words = zh_words + en_words

        # 停用词列表（扩展版）
        stopwords = {
            "的", "了", "是", "我", "你", "他", "她", "它", "们", "这", "那",
            "和", "与", "或", "但", "而", "在", "有", "为", "不", "上", "下",
            "中", "也", "就", "都", "说", "要", "会", "可", "以", "之", "于",
            "及", "其", "等", "被", "把", "从", "到", "去", "看", "想", "做",
            "好", "能", "得", "很", "太", "更", "最", "些", "后", "前", "内",
            "外", "时", "间", "年", "月", "日", "个", "种", "样", "次", "点",
            "面", "理", "例", "出", "现", "开", "始", "过", "程", "果", "如"
        }

        # 过滤停用词
        filtered = [w for w in words if w not in stopwords and len(w) >= 2]

        # 去重并返回前10个
        seen = set()
        result = []
        for w in filtered:
            if w not in seen:
                seen.add(w)
                result.append(w)
            if len(result) >= 10:
                break

        return result

    def _extract_core_meaning(self, text: str) -> str:
        """提取核心含义（取前两句或关键词组合）"""
        import re
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            return sentences[0][:60]
        return text[:60]
