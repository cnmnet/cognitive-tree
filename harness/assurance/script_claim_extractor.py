#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可验证主张提取器 (Day 12)
识别 "数字+比较级" 模式，自动生成测试代码骨架
"""

import re
import json
from typing import Any, Dict, List, Optional
from pathlib import Path
import sys
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from governance.config import Config


class ClaimExtractor:
    """
    可验证主张提取器
    
    识别文本中的可验证主张，自动生成测试代码骨架。
    """
    
    # 比较级模式 - 更严格的匹配
    PATTERNS = {
        "comparison": [
            # 匹配 "XX比YY提升/增加/下降/降低 XX%" 格式
            r'([\u4e00-\u9fff]{2,20})(?:比|较|与)([\u4e00-\u9fff]{2,20})(?:的)?(?:效率|成本|时间|性能|满意度|质量|速度|价格|收益|利润|产出|效果)?(?:提升|增加|提高|增长|下降|降低|减少|增长|优化)(?:了)?(\d+[\.\d]*)\s*(%|倍|个百分点)',
            # 匹配 "XX提升了XX%" 格式
            r'([\u4e00-\u9fff]{2,20})(?:的)?(?:效率|成本|时间|性能|满意度|质量|速度|价格|收益|利润|产出|效果)?(?:提升|增加|提高|增长|优化)(?:了)?(\d+[\.\d]*)\s*(%|倍|个百分点)',
            # 匹配 "XX从A%提升到B%" 格式
            r'([\u4e00-\u9fff]{2,20})(?:的)?(?:效率|成本|时间|性能|满意度|质量|速度|价格|收益|利润|产出|效果)?从(\d+[\.\d]*)\s*%?(?:提升|增加|提高|增长|优化)?到(\d+[\.\d]*)\s*%',
        ],
        "time": [
            # 匹配 "需要X天/小时" 格式
            r'(?:需要|耗时|花费|预计|约)(\d+[\.\d]*)\s*(天|小时|分钟|周|月)',
            # 匹配 "X天/小时内" 格式
            r'(\d+[\.\d]*)\s*(天|小时|分钟)(?:内|左右|以内)',
        ],
        "range": [
            # 匹配 "从X%到Y%" 格式
            r'从(\d+[\.\d]*)\s*%?(?:到|至)(\d+[\.\d]*)\s*%',
            # 匹配 "X%-Y%" 格式
            r'(\d+[\.\d]*)\s*%\s*[-~到至]\s*(\d+[\.\d]*)\s*%',
        ]
    }

    ASSERTION_VERBS = [
        "达到", "超过", "高于", "低于", "大于", "小于", "接近", "不足",
        "提升", "增加", "提高", "增长", "下降", "降低", "减少", "为", "是",
    ]

    STRONG_METRIC_PATTERN = r"(率|额|成本|利润|预算|价格|费用|时间|客户|用户|团队|公司|效率|性能|满意度|市场|收入|增速|比例|占比|数量|数据|指标|周期)"
    METRIC_SUFFIXES = (
        "率", "额", "成本", "利润", "预算", "价格", "费用", "时间", "客户", "用户",
        "团队", "公司", "效率", "性能", "满意度", "市场", "收入", "增速", "比例", "占比",
        "数量", "指标", "周期", "值",
    )
    UNIT_AFTER_NUMBER = "%元万亿美元次个条小时天周月年"
    TIME_UNIT_PATTERN = r"(天|小时|分钟|周|月|年)"
    SOURCE_MARKER_PATTERN = r"(\[arxiv\]|\[news\]|\[hf\]|\[external\]|https?://|来源[:：])"
    LOGIC_PATTERN = r"(因为[^，。；;]{2,}所以|由于[^，。；;]{2,}因此|如果[^，。；;]{2,}那么|只有[^，。；;]{2,}才)"
    
    def __init__(self, log_callback=None, engine=None):
        self.log = log_callback or print
        self.engine = engine
        self.claims: List[Dict] = []
    
    def _clean_text(self, text: str) -> str:
        """清洗文本，移除Markdown格式"""
        if not text:
            return ""
        
        # 移除 Markdown 标题（### 一、XXX）
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # 移除列表标记（- 、1. 等）
        text = re.sub(r'^[\s]*[-*•]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+[\.、]\s+', '', text, flags=re.MULTILINE)
        # 移除代码块
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # 移除粗体/斜体
        text = re.sub(r'\*\*.*?\*\*', '', text)
        text = re.sub(r'\*.*?\*', '', text)
        # 移除行内代码
        text = re.sub(r'`.*?`', '', text)
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取所有可验证主张
        """
        if not text or len(text) < 10:
            return []
        
        self.claims = []
        
        # 清洗文本
        clean_text = self._clean_text(text)
        
        # 提取比较型主张
        for pattern in self.PATTERNS["comparison"]:
            matches = re.finditer(pattern, clean_text)
            for match in matches:
                claim = self._parse_comparison(match, clean_text)
                if claim and self._is_valid_claim(claim):
                    self.claims.append(claim)
        
        # 提取时间型主张
        for pattern in self.PATTERNS["time"]:
            matches = re.finditer(pattern, clean_text)
            for match in matches:
                claim = self._parse_time(match, clean_text)
                if claim and self._is_valid_claim(claim):
                    self.claims.append(claim)
        
        # 提取范围型主张
        for pattern in self.PATTERNS["range"]:
            matches = re.finditer(pattern, clean_text)
            for match in matches:
                claim = self._parse_range(match, clean_text)
                if claim and self._is_valid_claim(claim):
                    self.claims.append(claim)

        # 提取绝对值与阈值主张（严格版）
        for claim in self._extract_absolute_claims(clean_text):
            if claim and self._is_valid_claim(claim):
                self.claims.append(claim)
        for claim in self._extract_threshold_claims(clean_text):
            if claim and self._is_valid_claim(claim):
                self.claims.append(claim)
        for claim in self._extract_source_claims(clean_text):
            if claim and self._is_valid_claim(claim):
                self.claims.append(claim)
        for claim in self._extract_logic_claims(clean_text):
            if claim and self._is_valid_claim(claim):
                self.claims.append(claim)
        
        # 去重（按原文去重）
        seen = set()
        unique_claims = []
        for claim in self.claims:
            key = claim.get("original", "")
            if key and key not in seen:
                seen.add(key)
                unique_claims.append(claim)
        self.claims = unique_claims
        
        # 为每个主张生成测试代码
        for claim in self.claims:
            claim["test_code"] = self._generate_test_code(claim)
            claim["confidence"] = self._compute_confidence(claim)
        
        return self.claims
    
    def _is_valid_claim(self, claim: Dict) -> bool:
        """验证主张是否有效"""
        # 必须有原文
        if not claim.get("original"):
            return False

        original = claim["original"]
        raw = claim.get("raw") or original

        # 原文长度不能太短
        if len(original) < 6:
            return False

        # 排除表格碎片与孤立数字
        if "|" in original or "｜" in original:
            return False
        if original.startswith(("%", "-", "—", "/", "\\", "|", "｜")):
            return False

        # 必须包含中文字符
        if not re.search(r'[\u4e00-\u9fff]', original):
            return False

        # 必须有明确的指标/时间上下文
        claim_type = claim.get("type", "")
        if claim_type == "time":
            if not re.search(self.TIME_UNIT_PATTERN, original + raw):
                return False
        elif claim_type == "source":
            if not re.search(self.SOURCE_MARKER_PATTERN, original + raw):
                return False
        elif claim_type == "logic":
            if len(original + raw) < 10 or not re.search(self.LOGIC_PATTERN, original + raw):
                return False
        else:
            if not re.search(self.STRONG_METRIC_PATTERN, original + raw):
                return False

        # 不能包含明显无意义的文本
        invalid_patterns = [
            r'^#+',  # 标题
            r'^\-+',  # 分隔线
            r'^\*+',  # 分隔线
            r'^=+',  # 分隔线
            r'^```',  # 代码块
            r'^###',  # Markdown标题
        ]
        for pattern in invalid_patterns:
            if re.match(pattern, claim["original"]):
                return False
        
        # 数值必须合理
        value = claim.get("value")
        if value is not None:
            if value < 0 or value > 10000:
                return False
        
        return True
    
    def _parse_comparison(self, match: re.Match, full_text: str) -> Optional[Dict]:
        """解析比较型主张"""
        groups = match.groups()
        if len(groups) < 3:
            return None
        
        # 尝试提取主语
        subject = groups[0] if len(groups) > 0 else ""
        
        # 提取数值
        value_str = None
        unit = ""
        for g in groups:
            if re.match(r'^\d+[\.\d]*$', str(g)):
                value_str = g
            elif g in ['%', '倍', '个百分点']:
                unit = g
        
        if value_str is None:
            return None
        
        try:
            value = float(value_str)
        except ValueError:
            return None
        
        # 如果值超过100且单位是%，可能是异常
        if value > 100 and unit == '%':
            return None
        
        return {
            "type": "comparison",
            "original": match.group(0)[:80],
            "subject": subject[:30] if subject else "",
            "value": value,
            "unit": unit,
            "raw": match.group(0)
        }
    
    def _parse_time(self, match: re.Match, full_text: str) -> Optional[Dict]:
        """解析时间型主张"""
        groups = match.groups()
        if len(groups) < 2:
            return None
        
        try:
            value = float(groups[0])
        except ValueError:
            return None
        
        unit = groups[1] if len(groups) > 1 else ""
        
        # 时间值不能太大（超过365天或8760小时）
        if unit == '天' and value > 365:
            return None
        if unit == '小时' and value > 8760:
            return None
        if unit == '分钟' and value > 525600:
            return None
        
        return {
            "type": "time",
            "original": match.group(0)[:60],
            "subject": "",
            "value": value,
            "unit": unit,
            "raw": match.group(0)
        }
    
    def _parse_range(self, match: re.Match, full_text: str) -> Optional[Dict]:
        """解析范围型主张"""
        groups = match.groups()
        if len(groups) < 2:
            return None
        
        try:
            min_val = float(groups[0])
            max_val = float(groups[1])
        except ValueError:
            return None
        
        # 范围值不能太大
        if min_val > 1000 or max_val > 1000:
            return None
        
        return {
            "type": "range",
            "original": match.group(0)[:60],
            "subject": "",
            "min_value": min_val,
            "max_value": max_val,
            "unit": "",
            "raw": match.group(0)
        }

    def _extract_absolute_claims(self, text: str) -> List[Dict[str, Any]]:
        """提取绝对值主张，例如“准确率达到95%”。"""
        claims = []
        for sentence in re.split(r'[。！？!?；;\n]', text or ""):
            if not sentence or len(sentence) < 6:
                continue
            if re.match(r'^\s*(如果|若|假设|当)', sentence):
                continue
            for number_match in re.finditer(r'\d+\.?\d*%?', sentence):
                start = number_match.start()
                context = sentence[max(0, start - 24):start]
                best_pos = -1
                verb = None
                for v in self.ASSERTION_VERBS:
                    pos = context.rfind(v)
                    if pos >= 0 and pos > best_pos:
                        best_pos = pos
                        verb = v
                if not verb:
                    continue
                if context[best_pos + len(verb):].strip():
                    continue
                prefix = context[:best_pos]
                digits = list(re.finditer(r'\d', prefix))
                if digits:
                    prefix = prefix[digits[-1].end():]
                entity = re.split(r'[\s，,。.；;、|：:（）()]+', prefix)[-1].strip()
                entity = re.sub(r'^[%|、，,。.；;：:0-9\s\-—/\\]+', '', entity).strip()
                entity = re.sub(r'^[但那而并又把将且的的是了在从于和或与们你你我他她它这那以个天周月年]+', '', entity).strip()
                if len(entity) < 2 or len(entity) > 30:
                    continue
                if not re.search(self.STRONG_METRIC_PATTERN, entity):
                    continue
                if not entity.endswith(self.METRIC_SUFFIXES):
                    continue
                value_str = number_match.group()
                if "%" not in value_str:
                    tail = sentence[number_match.end():number_match.end() + 2]
                    has_unit = bool(tail) and tail[0] in self.UNIT_AFTER_NUMBER
                    has_unit = has_unit or tail[:2] in ("小时", "美元", "欧元", "人民币")
                    if not has_unit:
                        continue
                value_str = number_match.group()
                try:
                    value = float(value_str.replace('%', '')) / 100.0 if '%' in value_str else float(value_str)
                except ValueError:
                    continue
                original = f"{entity}{verb}{value_str}"
                claims.append({
                    "type": "absolute",
                    "original": original,
                    "subject": entity,
                    "value": value,
                    "unit": "%" if "%" in value_str else "",
                    "raw": original,
                })
        return claims

    def _extract_threshold_claims(self, text: str) -> List[Dict[str, Any]]:
        """提取阈值主张，例如“毛利率低于15%”。"""
        claims = []
        patterns = [
            r'([^，,。.；;]{4,}?)\s*(?:从|由)\s*(\d+\.?\d*%?)\s*(?:上升|增长|提高|增加|下降到|降低|减少|下降)\s*(?:到|至)\s*(\d+\.?\d*%?)',
            r'([^，,。.；;]{3,}?)\s*(?:超过|高于|低于|大于|小于|不低于|不少于|不超过)\s*(\d+\.?\d*%?)',
            r'(?:如果|当|假设)\s*([^，,。.；;]{3,}?)\s*(?:低于|超过|不足|超过|至少|最多)\s*(\d+\.?\d*%?)',
            r'([^，,。.；;]{3,}?)\s*(?:不超过|不少于|低于|超过|至少|最多)\s*(\d+\.?\d*)\s*(元|美元|欧元|人民币|次|个|条|小时|天|周|月|年)',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                groups = match.groups()
                if len(groups) < 2:
                    continue
                entity = groups[0].strip()
                if len(entity) < 3:
                    continue
                if not re.search(self.STRONG_METRIC_PATTERN, entity):
                    continue
                if not entity.endswith(self.METRIC_SUFFIXES):
                    continue
                if len(groups) == 3:
                    original = f"{entity}从{groups[1]}变化到{groups[2]}"
                    try:
                        value = float(groups[1].replace('%', ''))
                    except ValueError:
                        continue
                else:
                    unit = groups[2] if len(groups) >= 3 else ""
                    original = f"{entity}{groups[1]}{unit}"
                    try:
                        value = float(groups[1].replace('%', ''))
                    except ValueError:
                        continue
                claims.append({
                    "type": "threshold",
                    "original": original,
                    "subject": entity,
                    "value": value,
                    "unit": "",
                    "raw": match.group(0),
                })
        return claims

    def _extract_source_claims(self, text: str) -> List[Dict[str, Any]]:
        """提取来源主张，例如带 [arxiv]/[news] 标记或 URL 的句子。"""
        claims = []
        for sentence in re.split(r'[。！？!?；;\n]', text or ""):
            sentence = sentence.strip()
            if len(sentence) < 6:
                continue
            if not re.search(self.SOURCE_MARKER_PATTERN, sentence):
                continue
            claims.append({
                "type": "source",
                "original": sentence[:120],
                "subject": "",
                "value": None,
                "unit": "",
                "raw": sentence,
            })
        return claims

    def _extract_logic_claims(self, text: str) -> List[Dict[str, Any]]:
        """提取逻辑主张，例如包含因为/所以、如果/那么等因果结构的句子。"""
        claims = []
        for sentence in re.split(r'[。！？!?；;\n]', text or ""):
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            if not re.search(self.LOGIC_PATTERN, sentence):
                continue
            claims.append({
                "type": "logic",
                "original": sentence[:120],
                "subject": "",
                "value": None,
                "unit": "",
                "raw": sentence,
            })
        return claims

    def _generate_test_code(self, claim: Dict) -> str:
        """为主张生成测试代码骨架"""
        claim_type = claim.get("type", "unknown")
        value = claim.get("value", 0)
        unit = claim.get("unit", "")
        subject = claim.get("subject", "指标")
        
        if claim_type == "comparison":
            code = f'''def test_claim():
    """验证主张: {claim.get('original', '')[:40]}"""
    
    # 实际值应从数据源获取
    actual_value = 0
    expected_value = {value}
    
    print(f"[测试] 期望值: {{expected_value}}{unit}")
    
    # 简单验证：实际值接近期望值（允许10%误差）
    if actual_value > 0:
        margin = expected_value * 0.1
        assert abs(actual_value - expected_value) <= margin, \\
            f"值偏差过大: {{actual_value}} vs {{expected_value}}"
        print(f"[PASS] {subject} 验证通过")
    else:
        # 数据源为空时跳过
        print(f"[SKIP] {subject} 无数据源，待核验")
        return None
    
    return True
'''
            return code
        
        elif claim_type == "time":
            unit = claim.get("unit", "天")
            code = f'''def test_claim():
    """验证时间估算: {claim.get('original', '')[:40]}"""
    
    # 实际执行时间（从日志获取）
    actual_time = 0
    expected_time = {value}
    
    print(f"[测试] 期望时间: {{expected_time}}{unit}")
    
    if actual_time > 0:
        assert actual_time <= expected_time * 1.2, \\
            f"时间超出预期: {{actual_time}} > {{expected_time}}"
        print(f"[PASS] 时间估算验证通过")
    else:
        print(f"[SKIP] 无实际时间数据，待核验")
        return None
    
    return True
'''
            return code
        
        elif claim_type == "range":
            min_val = claim.get("min_value", 0)
            max_val = claim.get("max_value", 10)
            code = f'''def test_claim():
    """验证范围: {claim.get('original', '')[:40]}"""
    
    # 实际值（从数据源获取）
    actual_value = 0
    
    print(f"[测试] 期望范围: [{min_val}, {max_val}]")
    
    if actual_value > 0:
        assert {min_val} <= actual_value <= {max_val}, \\
            f"值超出范围: {{actual_value}}"
        print(f"[PASS] 范围验证通过")
    else:
        print(f"[SKIP] 无数据源，待核验")
        return None
    
    return True
'''
            return code

        elif claim_type in ("source", "logic"):
            return '''def test_claim():
    """结构化主张: {claim.get('original', '')[:40]}"""
    print("[SKIP] 结构化主张，需人工核验")
    return None
'''

        else:
            return "# 无法生成测试代码：未知主张类型"
    
    def _compute_confidence(self, claim: Dict) -> float:
        """计算主张的置信度（0-1）"""
        confidence = 0.3
        
        # 有数值 +0.3
        if claim.get("value") is not None:
            confidence += 0.3
        
        # 有单位 +0.2
        if claim.get("unit"):
            confidence += 0.2
        
        # 有主语 +0.2
        if claim.get("subject"):
            confidence += 0.2
        
        return min(1.0, confidence)
    
    def extract_from_debate_result(self, debate_result: Dict) -> List[Dict]:
        """从辩论结果中提取所有可验证主张"""
        all_claims = []
        
        # 从各角色回答中提取
        for rd in debate_result.get("rounds", []):
            for answer in rd.get("answers", []):
                text = answer.get("answer", "")
                claims = self.extract(text)
                for claim in claims:
                    claim["source_role"] = answer.get("role", "未知")
                    claim["round"] = rd.get("round", 0)
                    all_claims.append(claim)
        
        # 从最终答案中提取
        final_answers = [
            debate_result.get("board_version", ""),
            debate_result.get("employee_version", ""),
            debate_result.get("novice_version", ""),
            debate_result.get("expert_version", ""),
        ]
        for text in final_answers:
            if text:
                claims = self.extract(text)
                for claim in claims:
                    claim["source_role"] = "首席发言人"
                    claim["source_type"] = "final_output"
                    all_claims.append(claim)
        
        # 去重
        seen = set()
        unique = []
        for claim in all_claims:
            key = claim.get("original", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(claim)
        
        return unique
    
    def generate_test_suite(self, claims: List[Dict], output_dir: Optional[Path] = None) -> Path:
        """为提取的主张生成完整的测试套件"""
        if output_dir is None:
            output_dir = Config.DATA_ROOT / "skills" / "_test_suite"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 只保留置信度大于0.5的主张
        valid_claims = [c for c in claims if c.get("confidence", 0) > 0.5]
        
        if not valid_claims:
            # 生成空测试文件
            test_file = output_dir / "test_claims.py"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write('#!/usr/bin/env python3\n')
                f.write('# -*- coding: utf-8 -*-\n')
                f.write('"""\n')
                f.write('无有效可验证主张\n')
                f.write(f'生成时间: {datetime.now().isoformat()}\n')
                f.write('"""\n\n')
                f.write('def main():\n')
                f.write('    print("[SKIP] 无有效可验证主张")\n')
                f.write('    return 0\n\n')
                f.write('if __name__ == "__main__":\n')
                f.write('    sys.exit(main())\n')
            return test_file
        
        # 生成主测试文件
        test_file = output_dir / "test_claims.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('#!/usr/bin/env python3\n')
            f.write('# -*- coding: utf-8 -*-\n')
            f.write('"""\n')
            f.write('自动生成的断言测试套件\n')
            f.write(f'生成时间: {datetime.now().isoformat()}\n')
            f.write(f'有效主张数量: {len(valid_claims)}\n')
            f.write('"""\n\n')
            f.write('import sys\n\n')
            
            # 生成测试函数
            for i, claim in enumerate(valid_claims, 1):
                f.write(f'\n# === 测试 {i}: {claim.get("original", "未知主张")[:40]} ===\n')
                f.write(claim.get("test_code", "# 测试代码生成失败\n"))
                f.write('\n')
            
            # 生成主函数
            f.write('def main():\n')
            f.write('    """运行所有测试"""\n')
            f.write('    print("=" * 60)\n')
            f.write('    print("运行断言测试套件")\n')
            f.write('    print("=" * 60)\n')
            f.write('    \n')
            f.write('    test_funcs = [\n')
            for i in range(1, len(valid_claims) + 1):
                f.write('        test_claim,\n')
            f.write('    ]\n')
            f.write('    \n')
            f.write('    passed = 0\n')
            f.write('    failed = 0\n')
            f.write('    skipped = 0\n')
            f.write('    \n')
            f.write('    for func in test_funcs:\n')
            f.write('        try:\n')
            f.write('            result = func()\n')
            f.write('            if result:\n')
            f.write('                passed += 1\n')
            f.write('            else:\n')
            f.write('                failed += 1\n')
            f.write('        except Exception as e:\n')
            f.write('            failed += 1\n')
            f.write('            print(f"[FAIL] {{e}}")\n')
            f.write('    \n')
            f.write('    print("=" * 60)\n')
            f.write('    print(f"通过: {{passed}} | 失败: {{failed}} | 跳过: {{skipped}}")\n')
            f.write('    return 0 if failed == 0 else 1\n')
            f.write('\n\n')
            f.write('if __name__ == "__main__":\n')
            f.write('    sys.exit(main())\n')
        
        # 生成元数据文件
        meta_file = output_dir / "claims_metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            serializable_claims = []
            for claim in valid_claims:
                clean = {k: v for k, v in claim.items() if k != "test_code"}
                serializable_claims.append(clean)
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "total_claims": len(valid_claims),
                "claims": serializable_claims
            }, f, ensure_ascii=False, indent=2)
        
        self.log(f"✅ 测试套件已生成: {test_file}")
        self.log(f"✅ 元数据已保存: {meta_file}")
        
        return test_file


def main():
    """命令行测试"""
    print("=" * 60)
    print("🔍 可验证主张提取器测试")
    print("=" * 60)
    
    extractor = ClaimExtractor()
    
    test_text = """
    根据分析，新方案比旧方案效率提升35%，时间成本降低20%。
    用户满意度从70%提升到85%。
    项目需要3天完成。
    """
    
    print("\n测试文本:")
    print(test_text)
    
    claims = extractor.extract(test_text)
    
    print(f"\n发现 {len(claims)} 个可验证主张:")
    for i, claim in enumerate(claims, 1):
        print(f"\n  {i}. 类型: {claim.get('type')}")
        print(f"     原文: {claim.get('original')}")
        print(f"     值: {claim.get('value', claim.get('min_value', 'N/A'))}")
        print(f"     置信度: {claim.get('confidence', 0):.2f}")
    
    print("\n" + "=" * 60)
    print("✅ 提取器测试完成")


if __name__ == "__main__":
    main()
