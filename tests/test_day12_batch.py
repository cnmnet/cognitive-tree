import tempfile
import unittest
from pathlib import Path

from data.storage import FileIO
from governance.config import Config
from harness.assurance.claim_extractor import ClaimExtractor, VerifiableClaim
from harness.assurance.day12_integration import Day12Integration
from harness.assurance.sandbox import SandboxExecutor
from harness.assurance.svr_mad import SVRMADValidator
from harness.contemplative import ContemplativeEngine
from harness.engine import CrystalEngine
from harness.processors.batch_processor import BatchProcessor


class _FakeAI:
    api_key = "test"

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "测试回答" * 50

    def chat_json(self, prompt, temperature=0.3, **kwargs):
        return {}


class TestDay12Batch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        (Config.DATA_ROOT / "系统日志").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "核心配置").mkdir(parents=True, exist_ok=True)
        self.engine = CrystalEngine(FileIO())

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_claim_extractor(self):
        claims = ClaimExtractor(engine=None).extract_from_text("新方案比旧方案效率提升35%")
        self.assertTrue(claims)

    def test_svr_mad(self):
        rounds = [
            {
                "round": 1,
                "answers": [
                    {"role": "激进者", "answer": "颠覆创新"},
                    {"role": "保守者", "answer": "稳健风险"},
                ],
            }
        ]
        result = SVRMADValidator(engine=None).validate_all_roles(rounds)
        self.assertIsInstance(result, dict)

    def test_sandbox(self):
        ok = SandboxExecutor(engine=None).execute_code("def main():\n    print('OK')\n")
        self.assertTrue(ok["success"])
        blocked = SandboxExecutor(engine=None).execute_code("import os\nos.system('rm -rf /')")
        self.assertFalse(blocked["success"])

    def test_sandbox_skip_not_pass(self):
        claim = VerifiableClaim(
            claim_id="SKIP-1",
            original_text="某指标无数据源",
            claim_type="absolute",
            test_code='def test_claim():\n    print("[SKIP] 无数据源，待核验")\n    return None\n',
        )
        result = SandboxExecutor(engine=None).execute_claim(claim)
        self.assertFalse(result["success"])
        self.assertEqual(result["verification_status"], "pending_review")

    def test_sandbox_assert_pass(self):
        claim = VerifiableClaim(
            claim_id="PASS-1",
            original_text="预算300+300+200=800",
            claim_type="absolute",
            test_code='def test_claim():\n    assert 300 + 300 + 200 == 800\n    print("[PASS] 预算自洽")\n',
        )
        result = SandboxExecutor(engine=None).execute_claim(claim)
        self.assertTrue(result["success"])
        self.assertEqual(result["verification_status"], "verified")

    def test_sandbox_assert_fail(self):
        claim = VerifiableClaim(
            claim_id="FAIL-1",
            original_text="预算300+300+200=900",
            claim_type="absolute",
            test_code='def test_claim():\n    assert 300 + 300 + 200 == 900\n    print("[PASS] 预算自洽")\n',
        )
        result = SandboxExecutor(engine=None).execute_claim(claim)
        self.assertFalse(result["success"])
        self.assertEqual(result["verification_status"], "failed")

    def test_day12_self_consistency_claims(self):
        annex = {
            "final_decision": "总预算800万元，分三阶段执行。",
            "resource_allocation": {"ratio": "70/30", "detail": "70%核心，30%弹性"},
            "budget": [
                {"item": "搭建", "amount": "300万", "note": ""},
                {"item": "迭代", "amount": "300万", "note": ""},
                {"item": "推广", "amount": "200万", "note": ""},
            ],
        }
        judge = {
            "role_scorecard": [
                {"role": "激进者", "contribution_percent": 8},
                {"role": "保守者", "contribution_percent": 18},
                {"role": "结构主义者", "contribution_percent": 20},
                {"role": "百灵鸟", "contribution_percent": 15},
                {"role": "取经者", "contribution_percent": 20},
                {"role": "奇谋者", "contribution_percent": 15},
                {"role": "延安智者", "contribution_percent": 4},
            ]
        }
        result = Day12Integration(self.engine, _FakeAI()).process_text(
            "这是没有可提取主张的文本。",
            [],
            decision_annex=annex,
            judge_audit=judge,
        )
        self.assertGreaterEqual(result["verified_count"], 3)
        self.assertGreaterEqual(result["asserted_count"], 3)
        self.assertIn("贡献度合计", result["claim_verification_summary"])

    def test_instantiation(self):
        ai = _FakeAI()
        Day12Integration(self.engine, ai)
        ContemplativeEngine(ai, self.engine)
        BatchProcessor(ai, lambda message, level="system": None)


if __name__ == "__main__":
    unittest.main()
