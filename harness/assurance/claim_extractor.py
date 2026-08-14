#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from harness.engine import CrystalEngine

@dataclass
class VerifiableClaim:
    """可验证主张的数据结构"""
    claim_id: str
    original_text: str
    claim_type: str  # "comparative", "absolute", "threshold"
    entity_a: Optional[str] = None
    entity_b: Optional[str] = None
    metric: Optional[str] = None
    value: Optional[float] = None
    comparison: Optional[str] = None  # ">", "<", ">=", "<=", "=="
    test_code: str = ""
    verified: bool = False
    result: Optional[Dict[str, Any]] = field(default_factory=dict)


class ClaimExtractor:
    """
    可验证主张提取器
    识别"数字+比较级"模式，自动生成测试代码骨架
    """

    # 数字模式：匹配整数、小数、百分比
    NUMBER_PATTERN = r'(\d+\.?\d*%?|\d+%?)'

    # 比较级模式（增强版：要求完整句子上下文）
    COMPARISON_PATTERNS = [
        r'比\s*([^，,。.；;]+?)\s*([高多低少好差优劣强弱大小])\s*' + NUMBER_PATTERN,
        r'([^，,。.；;]+?)\s*([高于|低于|大于|小于|超过|不足|接近|达到])\s*' + NUMBER_PATTERN,
        r'([^，,。.；;]+?)\s*的\s*([^，,。.；;]+?)\s*比\s*([^，,。.；;]+?)\s*([高多低少])\s*' + NUMBER_PATTERN,
        r'([^，,。.；;]+?)\s*从\s*' + NUMBER_PATTERN + r'\s*([提升|降低|增长|下降])\s*到\s*' + NUMBER_PATTERN,
    ]

    # 关键词映射
    COMPARISON_MAP = {
        "高于": ">", "大于": ">", "超过": ">", "高": ">",
        "低于": "<", "小于": "<", "不足": "<", "低": "<",
        "达到": "==", "接近": "≈", "等于": "==",
        "提升": "increase", "增长": "increase",
        "降低": "decrease", "下降": "decrease"
    }

    ASSERTION_VERBS = [
        "达到", "超过", "高于", "低于", "大于", "小于", "接近", "不足",
        "提升", "增加", "提高", "增长", "下降", "降低", "减少", "为", "是",
    ]

    METRIC_KEYWORDS = [
        "率", "额", "成本", "利润", "预算", "价格", "费用", "时间", "客户", "用户",
        "团队", "公司", "效率", "性能", "满意度", "市场", "收入", "增速", "比例", "占比",
        "数", "量", "元", "小时", "天", "周", "月", "年", "个", "次", "条", "人", "万", "亿",
    ]

    STRONG_METRIC_PATTERN = r"(率|额|成本|利润|预算|价格|费用|时间|客户|用户|团队|公司|效率|性能|满意度|市场|收入|增速|比例|占比|数量|数据|指标|周期)"

    def __init__(self, engine: 'CrystalEngine' = None):
        self.engine = engine
        self._claim_counter = 0

    def extract_from_text(self, text: str) -> List[VerifiableClaim]:
        """
        从文本中提取所有可验证主张
        """
        from harness.assurance.script_claim_extractor import ClaimExtractor as ScriptClaimExtractor
        script_claims = ScriptClaimExtractor(engine=self.engine).extract(text or "")
        claims = []
        for c in script_claims:
            claim = VerifiableClaim(
                claim_id=f"CLAIM-{self._claim_counter + 1:04d}",
                original_text=c.get("original") or c.get("raw") or "",
                claim_type=c.get("type", "absolute"),
                entity_a=c.get("subject") or "",
                value=c.get("value"),
                test_code=c.get("test_code", ""),
            )
            claims.append(claim)
            self._claim_counter += 1

        return claims

    def _extract_comparative_claims(self, text: str) -> List[VerifiableClaim]:
        """提取比较级主张"""
        claims = []

        # 模式：A 比 B 高/低 X%
        pattern = r'([^，,。.；;]+?)\s*比\s*([^，,。.；;]+?)\s*([高多低少好差优劣强弱大小]+)\s*(\d+\.?\d*%?)'
        matches = re.findall(pattern, text)
        for match in matches:
            entity_a = match[0].strip()
            entity_b = match[1].strip()
            direction = match[2].strip()
            value_str = match[3].strip()

            # 解析数值
            value = self._parse_number(value_str)
            if value is None:
                continue
            if len(entity_a) < 2 or len(entity_b) < 2:
                continue
            if not re.search(self.STRONG_METRIC_PATTERN, entity_a + entity_b):
                continue

            # 确定比较方向
            comp = ">" if direction in ["高", "多", "好", "优", "强", "大"] else "<"

            claim = VerifiableClaim(
                claim_id=f"CLAIM-{self._claim_counter + 1:04d}",
                original_text=f"{entity_a}比{entity_b}{direction}{value_str}",
                claim_type="comparative",
                entity_a=entity_a,
                entity_b=entity_b,
                metric=direction,
                value=value,
                comparison=comp
            )
            claims.append(claim)
            self._claim_counter += 1

        return claims

    def _extract_absolute_claims(self, text: str) -> List[VerifiableClaim]:
        """提取绝对值主张（如“准确率达到95%”），只接受完整句子里的指标断言。"""
        claims = []

        for sentence in re.split(r'[。！？!?；;\n]', text or ""):
            if not sentence or len(sentence) < 6:
                continue
            if re.match(r'^\s*(如果|若|假设|当)', sentence):
                continue
            for number_match in re.finditer(r'\d+\.?\d*%?', sentence):
                start = number_match.start()
                context = sentence[max(0, start - 14):start]
                best_pos = -1
                verb = None
                for v in self.ASSERTION_VERBS:
                    pos = context.rfind(v)
                    if pos >= 0 and pos > best_pos:
                        best_pos = pos
                        verb = v
                if not verb:
                    continue
                prefix = context[:best_pos]
                digits = list(re.finditer(r'\d', prefix))
                if digits:
                    prefix = prefix[digits[-1].end():]
                entity = re.split(r'[\s，,。.；;、]+', prefix)[-1].strip()
                entity = re.sub(
                    r'^[但那而并又把将且的的是了在从于和或与们你你我他她它这那]+',
                    '',
                    entity
                ).strip()
                entity = re.sub(r'^[%|、，,。.；;：:0-9\s\-—/\\]+', '', entity).strip()
                if len(entity) < 2 or len(entity) > 30:
                    continue
                if not re.search(self.STRONG_METRIC_PATTERN, entity):
                    continue
                value = self._parse_number(number_match.group())
                if value is None:
                    continue
                claim = VerifiableClaim(
                    claim_id=f"CLAIM-{self._claim_counter + 1:04d}",
                    original_text=f"{entity}{verb}{number_match.group()}",
                    claim_type="absolute",
                    entity_a=entity,
                    value=value
                )
                claims.append(claim)
                self._claim_counter += 1

        return claims

    def _extract_threshold_claims(self, text: str) -> List[VerifiableClaim]:
        """
        提取阈值主张（增强版：确保提取的是完整主张）

        核心改进：
        1. 数字必须与完整句子一起提取
        2. 不能单独提取孤立数字
        3. 句子必须包含明确的"主语 + 谓语 + 宾语"
        """
        claims = []

        # ===== 修复点：只匹配完整句子中的数字 =====
        patterns = [
            # 示例：客户流失率从 5% 上升到 18%
            r'([^，,。.；;]{4,}?)\s*(?:从|由)\s*(\d+\.?\d*%?)\s*(?:上升|增长|提高|增加|下降到|降低|减少|下降)\s*(?:到|至)\s*(\d+\.?\d*%?)',

            # 示例：准确率超过 95%
            r'([^，,。.；;]{3,}?)\s*(?:超过|高于|低于|大于|小于|不低于|不少于|不超过)\s*(\d+\.?\d*%?)',

            # 示例：如果三项总和低于 15，说明精力不足
            r'(?:如果|当|假设)\s*([^，,。.；;]{3,}?)\s*(?:低于|超过|不足|超过|至少|最多)\s*(\d+\.?\d*%?)',

            # 示例：预算限制在 100 元以内
            r'([^，,。.；;]{3,}?)\s*(?:不超过|不少于|低于|超过|至少|最多)\s*(\d+\.?\d*)\s*(?:元|美元|欧元|人民币|次|个|条|小时|天|周|月|年)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 2:
                    entity = match[0].strip()
                    if len(match) == 3:
                        # 从A到B的变化
                        value_text = f"{match[1]}→{match[2]}"
                        claim_text = f"{entity}从{match[1]}变化到{match[2]}"
                    else:
                        value_text = match[1]
                        claim_text = f"{entity}{match[1]}"

                    # 跳过过短或非指标类实体（防止误抓）
                    if len(entity) < 3:
                        continue
                    if not re.search(self.STRONG_METRIC_PATTERN, entity):
                        continue

                    value = self._parse_number(value_text)
                    if value is None:
                        continue

                    claim = VerifiableClaim(
                        claim_id=f"CLAIM-{self._claim_counter + 1:04d}",
                        original_text=claim_text[:100],
                        claim_type="threshold",
                        entity_a=entity[:50],
                        value=value
                    )
                    claims.append(claim)
                    self._claim_counter += 1

        return claims

    def _filter_valid_claims(self, claims: List[VerifiableClaim]) -> List[VerifiableClaim]:
        """
        过滤掉无效主张

        规则：
        1. 主张长度必须 >= 10 个字符（排除"低于15"这类片段）
        2. 主张必须包含至少一个中文字符（排除纯数字）
        3. 主张不能是孤立的数字
        """

        filtered = []

        for claim in claims:
            text = claim.original_text

            # 规则1：长度检查
            if len(text) < 6:
                continue

            # 规则2：必须包含中文字符
            if not re.search(r'[\u4e00-\u9fff]', text):
                continue

            # 规则3：不能只是数字+单位
            if re.match(r'^[\d.%]+\s*(元|美元|%|次|个|条|小时|天|周|月|年)?$', text):
                continue

            # 规则3.5：剔除以虚词开头的碎片
            if re.match(r'^[但那而并又把将且的的是了在从于和或与们你你我他她它这那]', text):
                continue

            # 规则4：必须有明确的主语（常见主语列表 + 指标关键词）
            has_subject = bool(re.search(self.STRONG_METRIC_PATTERN, text)) or any(kw in text for kw in [
                '成本', '价格', '费用', '预算', '支出',
                '准确率', '成功率', '有效率', '覆盖率',
                '客户', '用户', '团队', '公司',
                '他', '她', '我', '你', '我们', '你们',
                '增长率', '流失率', '转化率', '满意度',
                '爬', '刷', '去', '选', '做', '走', '看'
            ])
            if not has_subject:
                continue

            filtered.append(claim)

        return filtered

    def _parse_number(self, text: str) -> Optional[float]:
        """解析数字（支持百分比）"""
        text = text.strip()
        if not text:
            return None

        # 处理百分比
        is_percent = '%' in text
        text = text.replace('%', '').strip()

        try:
            value = float(text)
            if is_percent:
                value = value / 100.0
            return value
        except ValueError:
            return None

    def _generate_test_code(self, claim: VerifiableClaim) -> str:
        """为主张生成测试代码骨架"""
        if claim.claim_type == "comparative":
            return f'''def test_{claim.claim_id.lower()}():
    """
    验证：{claim.original_text}
    断言：{claim.entity_a} {claim.comparison} {claim.entity_b} (差值: {claim.value})
    """
    # TODO: 实现具体的验证逻辑
    # value_a = get_value("{claim.entity_a}")
    # value_b = get_value("{claim.entity_b}")
    # assert value_a {claim.comparison} value_b, f"{{value_a}} 不满足 {claim.comparison} {{value_b}}"
    pass
'''
        elif claim.claim_type == "absolute":
            return f'''def test_{claim.claim_id.lower()}():
    """
    验证：{claim.original_text}
    断言：{claim.entity_a} 的值为 {claim.value}
    """
    # TODO: 实现具体的验证逻辑
    # actual = get_value("{claim.entity_a}")
    # assert abs(actual - {claim.value}) < 0.01, f"期望 {{actual}} == {claim.value}"
    pass
'''
        else:
            return f'''def test_{claim.claim_id.lower()}():
    """
    验证：{claim.original_text}
    """
    # TODO: 实现具体的验证逻辑
    pass
'''


# =============================================================================
# 12.2 SVR-MAD 贝叶斯后验验证
# =============================================================================

