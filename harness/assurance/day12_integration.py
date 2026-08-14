#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from external.ai_client import AIClient
from harness.engine import CrystalEngine
from harness.assurance.claim_extractor import ClaimExtractor, VerifiableClaim
from harness.assurance.m3mad import M3MADBench, M3MADBenchResult
from harness.assurance.sandbox import SandboxExecutor
from harness.assurance.svr_mad import SVRMADValidator

class Day12Integration:
    """
    Day 12 功能集成类
    将所有新增功能集成到现有系统
    """
    
    def __init__(self, engine: 'CrystalEngine', ai_client: 'AIClient'):
        self.engine = engine
        self.ai = ai_client
        self.claim_extractor = ClaimExtractor(engine)
        self.svrmad_validator = SVRMADValidator(engine)
        self.sandbox = SandboxExecutor(engine)
        self.m3mad = M3MADBench(engine, ai_client)
    
    def process_text(self, text: str, debate_rounds: List[Dict] = None,
                     decision_annex: Dict = None, judge_audit: Dict = None) -> Dict[str, Any]:
        """
        处理文本，执行完整的 Day 12 流程
        
        Args:
            text: 要分析的文本
            debate_rounds: 辩论轮次数据（用于 SVR-MAD）
            decision_annex: 决策附录（用于预算/资源比例自洽校验）
            judge_audit: 法官裁决（用于贡献度合计自洽校验）
        """
        # 1. 提取主张
        claims = self.claim_extractor.extract_from_text(text)
        claims.extend(self._build_self_consistency_claims(claims, judge_audit, decision_annex))
        
        # 2. SVR-MAD 验证（如果有辩论数据）
        posterior_probs = {}
        most_reliable = ("未知", 0.0)
        if debate_rounds:
            posterior_probs = self.svrmad_validator.validate_all_roles(debate_rounds)
            most_reliable = self.svrmad_validator.get_most_reliable_role(debate_rounds)
        
        # 3. 沙盒执行（只执行数字类主张；来源/逻辑主张做结构化核验）
        sandbox_results = []
        numeric_claims = [c for c in claims if c.claim_type in ("comparative", "absolute", "threshold")]
        if numeric_claims:
            sandbox_results = self.sandbox.execute_claims(numeric_claims)
        result_by_claim_id = {r.get("claim_id"): r for r in sandbox_results}
        for claim in claims:
            claim_result = result_by_claim_id.get(claim.claim_id)
            if claim.claim_type in ("comparative", "absolute", "threshold"):
                status = (claim_result or {}).get("verification_status", "pending_review")
                claim.verified = status == "verified"
                claim.result = claim_result or {"verification_status": "pending_review"}
            elif claim.claim_type == "source":
                claim.verified = False
                claim.result = {"status": "pending_review", "verification_status": "pending_review"}
            elif claim.claim_type == "logic":
                claim.verified = False
                claim.result = {"status": "pending_review", "verification_status": "pending_review"}
        
        # 4. M3MAD-Bench 评估（如果有辩论数据）
        m3mad_result = M3MADBenchResult()
        if debate_rounds:
            mock_result = {"question": "验证问题", "rounds": debate_rounds}
            m3mad_result = self.m3mad.evaluate(mock_result)
        
        # 5. 构建增强报告
        claims_data = [c.__dict__ for c in claims]
        passed_count = sum(1 for c in claims if c.verified)
        pending_count = sum(1 for c in claims if c.result.get("verification_status") == "pending_review")
        failed_count = sum(1 for c in claims if c.result.get("verification_status") == "failed")
        asserted_count = sum(1 for c in claims if c.result.get("verification_status") in ("verified", "failed"))
        numeric_count = len(numeric_claims)
        source_count = sum(1 for c in claims if c.claim_type == "source")
        logic_count = sum(1 for c in claims if c.claim_type == "logic")
        sandbox_passed = sum(1 for r in sandbox_results if r.get("success", False))
        sandbox_pending = sum(1 for r in sandbox_results if r.get("verification_status") == "pending_review")
        current_summary = {
            "total": len(sandbox_results),
            "passed": sandbox_passed,
            "failed": sum(1 for r in sandbox_results if r.get("verification_status") == "failed"),
            "pending": sandbox_pending,
            "pass_rate": sandbox_passed / len(sandbox_results) if sandbox_results else 0.0,
            "avg_execution_time": (
                sum(r.get("execution_time", 0) for r in sandbox_results) / len(sandbox_results)
                if sandbox_results else 0.0
            ),
        }

        enhanced_report = {
            "claims_extracted": len(claims),
            "verified_count": passed_count,
            "pending_review_count": pending_count,
            "failed_count": failed_count,
            "asserted_count": asserted_count,
            "numeric_claim_count": numeric_count,
            "source_claim_count": source_count,
            "logic_claim_count": logic_count,
            "claims": claims_data,
            "svrmad": {
                "posterior_probabilities": posterior_probs,
                "most_reliable_role": most_reliable[0],
                "most_reliable_score": most_reliable[1]
            },
            "sandbox": {
                "results": sandbox_results,
                "summary": current_summary
            },
            "sources": self._extract_sources(text),
            "m3mad_bench": m3mad_result.to_dict(),
            "claim_verification_summary": self._generate_claim_summary(claims)
        }
        
        # 记录到进化日志
        if self.engine:
            self.engine.log_evolution_event(
                "day12_verification",
                {
                    "claims_count": len(claims),
                    "verified_count": enhanced_report["verified_count"],
                    "m3mad_overall": m3mad_result.overall_score,
                    "trigger": "day12_processing"
                }
            )

        # ===== Day 7: M3MAD 三维评分回写 =====
        if self.engine:
            self.engine.log_evolution_event(
                "m3mad_result",
                {
                    "text_sample": text[:200],
                    **m3mad_result.to_dict(),
                    "trigger": "day12_processing"
                }
            )
        
        return enhanced_report
    
    def process_debate_result(self, debate_result: Dict) -> Dict[str, Any]:
        """处理辩论结果（兼容旧接口）"""
        all_answers = []
        for rd in debate_result.get("rounds", []):
            for ans in rd.get("answers", []):
                all_answers.append(ans.get("answer", ""))
        
        combined_text = " ".join(all_answers)
        return self.process_text(combined_text, debate_result.get("rounds", []))
    
    def _parse_amount(self, text: Any) -> Optional[float]:
        """从金额文本中解析数字（忽略万元/元等单位）。"""
        if not text:
            return None
        m = re.search(r"\d+(?:\.\d+)?", str(text))
        return float(m.group(0)) if m else None

    def _find_budget_total(self, decision_annex: Dict) -> Optional[float]:
        """从决策附录中寻找总预算口径。"""
        texts = []
        final = (decision_annex or {}).get("final_decision") or ""
        resource = (decision_annex or {}).get("resource_allocation") or {}
        texts.append(final)
        texts.append(resource.get("detail") or "")
        for text in texts:
            if not text:
                continue
            for m in re.finditer(r"(总预算|预算合计|合计|总投入|总投资)\s*[为是：: ]*\s*(\d+(?:\.\d+)?)", text):
                return float(m.group(2))
            for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:万)?元", text):
                ctx = text[max(0, m.start() - 12):m.start()]
                if any(k in ctx for k in ("总", "合计")):
                    return float(m.group(1))
        return None

    def _build_self_consistency_claims(self, claims: List[VerifiableClaim],
                                       judge_audit: Dict = None,
                                       decision_annex: Dict = None) -> List[VerifiableClaim]:
        """构造报告内可自洽校验的主张，避免把无数据源内容冒充为已通过。"""
        new_claims: List[VerifiableClaim] = []

        def next_id() -> str:
            return f"SELF-{len(claims) + len(new_claims) + 1:04d}"

        scorecard = (judge_audit or {}).get("role_scorecard") or []
        percents = [
            item.get("contribution_percent")
            for item in scorecard
            if isinstance(item.get("contribution_percent"), (int, float))
        ]
        if len(percents) >= 2:
            total = sum(percents)
            values_repr = ", ".join(str(v) for v in percents)
            new_claims.append(VerifiableClaim(
                claim_id=next_id(),
                original_text=f"角色贡献度合计应等于100%（当前{total:.1f}%）",
                claim_type="absolute",
                entity_a="角色贡献度",
                value=100.0,
                test_code=f'''def test_claim():
    values = [{values_repr}]
    total = sum(values)
    assert abs(total - 100.0) <= 0.5, f"贡献度合计 {{total}} != 100"
    print("[PASS] 贡献度合计自洽")
''',
            ))

        resource = (decision_annex or {}).get("resource_allocation") or {}
        ratio_text = str(resource.get("ratio") or "")
        ratios = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", ratio_text)]
        if len(ratios) >= 2:
            values = ratios[:2]
            total = sum(values)
            values_repr = ", ".join(str(v) for v in values)
            new_claims.append(VerifiableClaim(
                claim_id=next_id(),
                original_text=f"资源分配比例合计应等于100%（当前{total:.1f}%）",
                claim_type="absolute",
                entity_a="资源分配比例",
                value=100.0,
                test_code=f'''def test_claim():
    values = [{values_repr}]
    total = sum(values)
    assert abs(total - 100.0) <= 0.5, f"资源分配比例合计 {{total}} != 100"
    print("[PASS] 资源分配比例自洽")
''',
            ))

        budget = (decision_annex or {}).get("budget") or []
        amounts = [
            amount for amount in (
                self._parse_amount(item.get("amount"))
                for item in budget
                if isinstance(item, dict)
            )
            if amount is not None
        ]
        if len(amounts) >= 2:
            total_hint = self._find_budget_total(decision_annex)
            sum_amount = sum(amounts)
            values_repr = ", ".join(str(v) for v in amounts)
            if total_hint is not None:
                new_claims.append(VerifiableClaim(
                    claim_id=next_id(),
                    original_text=f"预算分项合计应等于总预算（分项合计{sum_amount:.1f}，总预算{total_hint:.1f}）",
                    claim_type="absolute",
                    entity_a="预算分项",
                    value=total_hint,
                    test_code=f'''def test_claim():
    values = [{values_repr}]
    total = sum(values)
    expected = {total_hint}
    assert abs(total - expected) <= 0.01, f"预算合计 {{total}} != {{expected}}"
    print("[PASS] 预算分项合计自洽")
''',
                ))
            else:
                new_claims.append(VerifiableClaim(
                    claim_id=next_id(),
                    original_text=f"预算分项合计{sum_amount:.1f}，待总预算口径核验",
                    claim_type="absolute",
                    entity_a="预算分项",
                    value=None,
                    test_code='''def test_claim():
    print("[SKIP] 未找到总预算口径，待人工核验")
    return None
''',
                ))
        return new_claims

    def _extract_sources(self, text: str) -> List[str]:
        """从文本中抽取外部来源标记与 URL，用于报告来源索引。"""
        sources = []
        for m in re.finditer(r'\[(arxiv|news|hf|external)\][^\n]{0,100}', text or ""):
            item = m.group(0).strip()
            if item and item not in sources:
                sources.append(item)
        for m in re.finditer(r'https?://\S+', text or ""):
            item = m.group(0).strip('.,;；:：')
            if item and item not in sources:
                sources.append(item)
        return sources[:50]

    def _generate_claim_summary(self, claims: List[VerifiableClaim]) -> str:
        """生成主张验证摘要"""
        if not claims:
            return "未提取到可验证主张"

        verified = sum(1 for c in claims if c.verified)
        pending = sum(1 for c in claims if c.result.get("verification_status") == "pending_review")
        failed = sum(1 for c in claims if c.result.get("verification_status") == "failed")
        total = len(claims)

        lines = [
            "📋 可验证主张提取结果：",
            f"  共提取 {total} 条主张",
            f"  沙盒验证通过 {verified} 条，待人工核验 {pending} 条，未通过 {failed} 条",
            "",
            "  主张列表："
        ]

        for claim in claims[:5]:
            if claim.verified:
                status = "✅"
            elif claim.result.get("verification_status") == "failed":
                status = "❌"
            else:
                status = "⏳"
            lines.append(f"  {status} {claim.original_text}")

        if len(claims) > 5:
            lines.append(f"  ... 还有 {len(claims) - 5} 条")

        return "\n".join(lines)


