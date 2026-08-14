import tempfile
import unittest
from pathlib import Path

from harness.services import save_report_to_desktop
from harness.reporting import (
    CompressionContract,
    _extract_step_blocks,
    _join_broken_lines,
    build_debate_report_markdown,
    build_quick_view_report,
    compress_report_with_contract,
    limit_original_report,
    polish_report_markdown,
    validate_compressed,
)


class FakeAI:
    api_key = "test"

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "压缩后的完整报告，结构完整，内容精炼。" * 20 + "。"


class FakeAIValidAfterRetry:
    api_key = "test"

    def __init__(self):
        self.calls = 0

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return "太短，不满足结构。"
        return "## 结论\n选B。\n## 理由\n现金流更快。\n## 下一步\n先试点再规模化。\n## 止损\n毛利率低于15%止损。"


class FakeAIShortStructured:
    api_key = "test"

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "## 结论\n选B。\n## 理由\n现金流更快。\n## 下一步\n先试点。"


class TestReporting(unittest.TestCase):
    def test_build_debate_report_markdown(self):
        result = {
            "rounds": [
                {"round": 1, "answers": [{"role": "激进者", "answer": "方案一"}]}
            ],
            "elegant_epilogue": "儒雅结语",
            "decision_annex": {
                "final_decision": "主攻B，A作为赋能工具",
                "resource_allocation": {"ratio": "70/30", "detail": "B为主攻方向"},
                "budget": [{"item": "B线", "amount": "700万", "note": "主攻"}],
                "timeline": [{"phase": "0-3个月", "actions": "试点", "milestone": "验收"}],
                "stop_loss": [{"metric": "毛利率", "threshold": "15%", "action": "止损"}],
                "risk_control": [{"risk": "合规", "level": "P0", "mitigation": "法务"}],
                "acceptance_criteria": ["首期验收通过"],
                "owners": [{"role": "项目负责人", "responsibility": "统筹"}],
            },
        }
        md = build_debate_report_markdown(
            "测试问题",
            result,
            "老板版内容",
            "员工版内容",
            "新人版内容",
            "专家版内容",
            {"role_scorecard": [{"role": "激进者", "status": "adopted"}], "final_verdict": "采纳"},
        )
        self.assertIn("# 📋 辩论报告", md)
        self.assertIn("## 大法官裁决", md)
        self.assertIn("儒雅结语", md)
        self.assertIn("## 第二部分 · 决策附录（可执行版）", md)
        self.assertIn("### 最终决策", md)
        self.assertIn("### 止损线", md)
        self.assertIn("主攻B，A作为赋能工具", md)
        self.assertIn("报告生成时间", md)

    def test_polish_fallback(self):
        long_report = "这是一个很长的报告。" * 500
        polished = polish_report_markdown(long_report, ai_client=None, max_len=600)
        self.assertLessEqual(len(polished), 600)
        self.assertTrue(polished)

    def test_polish_with_ai(self):
        long_report = "这是一个很长的报告。" * 500
        polished = polish_report_markdown(long_report, ai_client=FakeAI(), max_len=600)
        self.assertTrue(polished)
        self.assertLessEqual(len(polished), 600)

    def test_contract_validation(self):
        contract = CompressionContract(max_chars=200, required_sections=["结论", "理由", "下一步"])
        ok, reasons = validate_compressed("结论：x\n理由：y\n下一步：z\n止损：w", contract)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])
        ok2, reasons2 = validate_compressed("只有一句话。", contract)
        self.assertFalse(ok2)
        self.assertTrue(any("结论" in r or "字数" in r for r in reasons2))

    def test_fallback_satisfies_contract(self):
        full = (
            "这是一段很长的铺垫。" * 40 +
            "## 终审裁决\n最终结论：选B。\n"
            "## 裁决理由\n理由：现金流更快，风险更低。\n"
            "## 30/60/90 天行动清单\n- **30天**：先做试点。\n- **60天**：验证毛利。\n"
            "## 止损\n毛利率低于15%即止损。"
        )
        contract = CompressionContract(max_chars=220, required_sections=["结论", "理由", "下一步"])
        out = compress_report_with_contract(full, ai_client=None, contract=contract)
        self.assertLessEqual(len(out), 220)
        for section in ("结论", "理由", "下一步", "止损"):
            self.assertIn(section, out)

    def test_retry_then_valid(self):
        full = "这是一个很长的报告。" * 200 + "止损线明确。"
        fake = FakeAIValidAfterRetry()
        contract = CompressionContract(max_chars=220, required_sections=["结论", "理由", "下一步"])
        out = compress_report_with_contract(full, ai_client=fake, contract=contract)
        self.assertEqual(fake.calls, 2)
        ok, reasons = validate_compressed(out, contract)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

    def test_validate_compressed_enforces_min_chars(self):
        contract = CompressionContract(max_chars=1000, min_chars=500, required_sections=["结论"])
        ok, reasons = validate_compressed("## 结论\n太短", contract)
        self.assertFalse(ok)
        self.assertIn("字数不足 500", reasons)

    def test_ai_best_kept_when_length_short(self):
        full = "这是一个很长的报告。" * 500
        contract = CompressionContract(
            max_chars=600,
            min_chars=500,
            required_sections=["结论", "理由", "下一步"],
            retries=1,
        )
        out = compress_report_with_contract(full, ai_client=FakeAIShortStructured(), contract=contract)
        self.assertIn("选B", out)
        self.assertNotIn("建议人工补充", out)

    def test_limit_original_report(self):
        short = "## 结论\n选B。\n## 理由\n现金流快。"
        self.assertEqual(limit_original_report(short), short)
        long = "这是一段很长的铺垫。" * 600 + "## 终审裁决\n最终结论：选B。\n## 裁决理由\n理由：现金流更快。\n## 30/60/90 天行动清单\n- **30天**：试点。"
        capped = limit_original_report(long, ai_client=None, max_chars=25000)
        self.assertLessEqual(len(capped), 25000)
        self.assertIn("结论", capped)

    def test_limit_original_report_keeps_novice_section(self):
        long = "这是一段很长的铺垫。" * 600
        long += "## 终审裁决\n最终结论：选B。\n## 裁决理由\n理由：现金流更快。\n## 30/60/90 天行动清单\n- **30天**：试点。\n"
        long += "## 首席发言人叙事\n### 新人版 - 通俗解释\n新人版内容：像家里花钱一样解释。\n"
        capped = limit_original_report(long, ai_client=None, max_chars=1000)
        self.assertLessEqual(len(capped), 1000)
        self.assertIn("通俗解释", capped)

    def test_save_report_original_not_truncated(self):
        question = "测试问题"
        result = {
            "rounds": [{"round": 1, "answers": [{"role": "激进者", "answer": "观点。"}]}],
            "elegant_epilogue": "儒雅笔谈内容。",
        }
        judge_audit = {"role_scorecard": [], "final_verdict": "终审裁决。"}
        board = "老板版内容。" * 4000
        employee = "员工版内容。" * 2000
        novice = "新人版内容。" * 2000
        expert = "专家版内容。" * 2000
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_report_to_desktop(
                question,
                result,
                board,
                employee,
                novice,
                expert,
                judge_audit,
                ai_client=None,
                log=lambda message, level="system": None,
                desktop_dir=Path(tmp),
            )
            original = Path(paths["original"]).read_text(encoding="utf-8")
            self.assertIn("新人版", original)
            self.assertIn("儒雅笔谈", original)
            full = build_debate_report_markdown(
                question, result, board, employee, novice, expert, judge_audit
            )
            self.assertEqual(original, full)

    def test_report_sandbox_three_state(self):
        result = {
            "rounds": [],
            "elegant_epilogue": "",
            "_day12": {
                "claims_extracted": 3,
                "verified_count": 1,
                "pending_review_count": 1,
                "failed_count": 1,
                "asserted_count": 2,
                "numeric_claim_count": 2,
                "source_claim_count": 0,
                "logic_claim_count": 0,
                "m3mad_bench": {"overall_score": 0.5},
                "claims": [
                    {
                        "original_text": "预算合计自洽",
                        "claim_type": "absolute",
                        "verified": True,
                        "result": {"verification_status": "verified"},
                    },
                    {
                        "original_text": "某指标无数据源",
                        "claim_type": "absolute",
                        "verified": False,
                        "result": {"verification_status": "pending_review"},
                    },
                    {
                        "original_text": "预算不匹配",
                        "claim_type": "absolute",
                        "verified": False,
                        "result": {"verification_status": "failed"},
                    },
                ],
            },
        }
        md = build_debate_report_markdown(
            "测试问题",
            result,
            "老板版内容",
            "员工版内容",
            "新人版内容",
            "专家版内容",
            {"role_scorecard": [], "final_verdict": "采纳"},
        )
        self.assertIn("✅ 通过", md)
        self.assertIn("⏳ 待人工核验", md)
        self.assertIn("❌ 失败", md)
        self.assertIn("已断言主张通过率", md)

    def test_report_performance_board_has_nine_roles(self):
        scorecard = [
            {"role": role, "status": "adopted", "contribution_percent": 10}
            for role in ("激进者", "保守者", "结构主义者", "百灵鸟", "取经者", "奇谋者", "延安智者")
        ]
        md = build_debate_report_markdown(
            "测试问题",
            {"rounds": [], "elegant_epilogue": ""},
            "老板版内容",
            "员工版内容",
            "新人版内容",
            "专家版内容",
            {"role_scorecard": scorecard, "final_verdict": "采纳"},
        )
        self.assertIn("| 大法官 |", md)
        self.assertIn("| 首席发言人 |", md)

    def test_quick_view(self):
        full = "这是一段很长的铺垫。" * 200 + "## 终审裁决\n最终结论：选B。\n## 裁决理由\n理由：现金流更快。\n## 30/60/90 天行动清单\n- **30天**：试点。\n## 止损\n低于15%止损。"
        quick = build_quick_view_report(full, ai_client=None, max_chars=800)
        self.assertLessEqual(len(quick), 800)
        for section in ("结论", "理由", "下一步"):
            self.assertIn(section, quick)

    def test_helpers(self):
        text = (
            "第一步：制定完整方案并明确责任人。\n"
            "第二步：执行方案并跟踪进度。\n"
            "第三步：复盘结果并沉淀经验。"
        )
        self.assertGreaterEqual(len(_extract_step_blocks(text)), 3)
        joined = _join_broken_lines("端到\n端到端")
        self.assertIn("端到端到端", joined)


if __name__ == "__main__":
    unittest.main()
