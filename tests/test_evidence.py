import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from governance.config import Config
from harness.evidence import EvidenceItem, EvidenceOrchestrator, EvidencePackage


class _FakeCrystal:
    id = "C001"
    title = "冷链合规"
    content = "医药冷链需 GSP 认证，温控改造周期约 6-9 个月"


class _FakeEngine:
    def get_associative_crystals(self, question, top_k=5):
        return [_FakeCrystal()]


class TestEvidenceOrchestrator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_fingerprint_is_stable(self):
        orch = EvidenceOrchestrator()
        a = orch.fingerprint("预算 700万 + 300万 = 1000万")
        b = orch.fingerprint("预算700万+300万=1000万")
        self.assertEqual(a, b)

    def test_arithmetic_gates_detect_good_and_bad_totals(self):
        orch = EvidenceOrchestrator()
        good = orch.run_arithmetic_gates("预算分配：A线 700万，B线 300万，合计 1000万。")
        bad = orch.run_arithmetic_gates("预算分配：A线 700万，B线 300万，合计 950万。")
        self.assertTrue(any(c["passed"] for c in good))
        self.assertTrue(any(not c["passed"] for c in bad))

    def test_percent_gate(self):
        orch = EvidenceOrchestrator()
        good = orch.run_arithmetic_gates("资源配比：30% + 40% + 30% = 100%")
        bad = orch.run_arithmetic_gates("资源配比：30% + 40% + 20% = 100%")
        self.assertTrue(any(c["type"] == "percent_sum" and c["passed"] for c in good))
        self.assertTrue(any(c["type"] == "percent_sum" and not c["passed"] for c in bad))

    def test_percent_gate_two_items(self):
        orch = EvidenceOrchestrator()
        checks = orch.run_arithmetic_gates("资源配比：70% + 30% = 100%")
        self.assertTrue(any(c["type"] == "percent_sum" and c["passed"] for c in checks))

    def test_unit_conversion_equation(self):
        orch = EvidenceOrchestrator()
        checks = orch.run_arithmetic_gates("A线 7000万 + B线 3000万 = 1亿")
        self.assertTrue(any(c["type"] == "explicit_equation" and c["passed"] for c in checks))

    def test_multiplication_equation(self):
        orch = EvidenceOrchestrator()
        checks = orch.run_arithmetic_gates("客单价 500 × 3万 = 1500万")
        self.assertTrue(any(c["type"] == "explicit_equation" and c["passed"] for c in checks))

    def test_percent_allocation_consistency(self):
        orch = EvidenceOrchestrator()
        good = orch.run_arithmetic_gates("A线 700万（70%），合计 1000万。")
        bad = orch.run_arithmetic_gates("A线 700万（80%），合计 1000万。")
        self.assertTrue(any(c["type"] == "percent_allocation" and c["passed"] for c in good))
        self.assertTrue(any(c["type"] == "percent_allocation" and not c["passed"] for c in bad))

    def test_growth_rate_consistency(self):
        orch = EvidenceOrchestrator()
        good = orch.run_arithmetic_gates("用户量从 10 万增长 30% 至 13 万。")
        bad = orch.run_arithmetic_gates("用户量从 10 万增长 30% 至 15 万。")
        self.assertTrue(any(c["type"] == "growth_rate" and c["passed"] for c in good))
        self.assertTrue(any(c["type"] == "growth_rate" and not c["passed"] for c in bad))

    def test_block_total_across_lines(self):
        orch = EvidenceOrchestrator()
        good = orch.run_arithmetic_gates("A线 700万\nB线 300万\n\n合计 1000万。")
        bad = orch.run_arithmetic_gates("A线 700万\nB线 300万\n\n合计 950万。")
        self.assertTrue(any(c["type"] == "block_total" and c["passed"] for c in good))
        self.assertTrue(any(c["type"] == "block_total" and not c["passed"] for c in bad))

    def test_budget_table_ratio_checks(self):
        orch = EvidenceOrchestrator()
        good = (
            "| 科目 | 金额（万元） | 占比 |\n"
            "|------|------|------|\n"
            "| A线直播 | 560 | 70% |\n"
            "| B线特医 | 160 | 20% |\n"
            "| 弹性储备 | 80 | 10% |\n"
            "| 合计 | 800 | 100% |\n"
        )
        bad = (
            "| 科目 | 金额（万元） | 占比 |\n"
            "|------|------|------|\n"
            "| B专业渠道 | 400 | 60% |\n"
            "| A直播电商 | 300 | 40% |\n"
            "| 机动资金 | 100 | 10% |\n"
            "| 合计 | 800 | 100% |\n"
        )
        good_ratio = [c for c in orch.run_arithmetic_gates(good) if c["type"] == "budget_ratio"]
        bad_ratio = [c for c in orch.run_arithmetic_gates(bad) if c["type"] == "budget_ratio"]
        self.assertEqual(len(good_ratio), 3)
        self.assertTrue(all(c["passed"] for c in good_ratio))
        self.assertEqual(len(bad_ratio), 3)
        self.assertTrue(all(not c["passed"] for c in bad_ratio))

    def test_stage_budget_checks(self):
        orch = EvidenceOrchestrator()
        good = (
            "第1-3个月 投入 300万元；第4-6个月 投入 300万元；"
            "第7-12个月 投入 200万元。总预算 800万元。"
        )
        bad = (
            "第1-3个月 投入 300万元；第4-6个月 投入 300万元；"
            "第7-12个月 投入 300万元。总预算 800万元。"
        )
        good_checks = [c for c in orch.run_arithmetic_gates(good) if c["type"] == "stage_budget_total"]
        bad_checks = [c for c in orch.run_arithmetic_gates(bad) if c["type"] == "stage_budget_total"]
        self.assertEqual(len(good_checks), 1)
        self.assertTrue(good_checks[0]["passed"])
        self.assertEqual(len(bad_checks), 1)
        self.assertFalse(bad_checks[0]["passed"])

    def test_assumption_grading(self):
        orch = EvidenceOrchestrator()
        grades = orch.grade_assumptions(
            "据 Gartner 报告，2026 年市场规模增长 30%。"
            "预计首批获客 3 万人。"
            "假设客单价 500 元，则月收入 1500 万。"
        )
        self.assertTrue(any(g["grade"] == "A" for g in grades))
        self.assertTrue(any(g["grade"] == "B" for g in grades))
        self.assertTrue(any(g["grade"] == "C" for g in grades))

    def test_dedupe_by_fingerprint(self):
        orch = EvidenceOrchestrator()
        items = [
            EvidenceItem("", "百度新闻", "冷链市场 2026", "市场规模 128 亿美元"),
            EvidenceItem("", "百度新闻", "冷链市场 2026", "市场规模 128 亿美元"),
        ]
        result = orch._dedupe(items)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].fingerprint)

    def test_build_package_from_internal_and_cache(self):
        cache_dir = Config.DATA_ROOT / "系统日志"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "external_sources_cache.json").write_text(
            json.dumps({
                "timestamp": "2026-08-10T00:00:00",
                "data": {
                    "news": [{
                        "title": "医药冷链市场持续增长",
                        "summary": "2026 年医药冷链市场规模预计达 128 亿美元",
                        "source": "百度新闻",
                        "url": "https://example.com/news/1",
                    }]
                },
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        orch = EvidenceOrchestrator(engine=_FakeEngine())
        package = orch.build_package("冷链医药市场值得投入吗？", max_items=5)
        self.assertGreaterEqual(len(package.items), 1)
        self.assertTrue(all(item.evidence_id.startswith("E") for item in package.items))
        sources = {item.source for item in package.items}
        self.assertTrue(sources & {"晶体库", "百度新闻"})

    def test_package_format_contains_evidence_ids(self):
        package = EvidencePackage(
            items=[EvidenceItem("E001", "晶体库", "物流成本", "大宗运输毛利持续下滑")],
            keywords=["物流"],
        )
        text = package.format_for_prompt()
        self.assertIn("[E001]", text)
        self.assertIn("证据包", text)

    def test_build_report_structure(self):
        orch = EvidenceOrchestrator(engine=_FakeEngine())
        report = orch.build_report(
            "方案一预算 700 万，方案二预算 300 万，合计 1000 万。"
            "预计 3 万用户。假设转化率 5%。",
            question="测试问题",
            package=EvidencePackage(
                items=[EvidenceItem("E001", "晶体库", "预算", "合计应等于分项之和")],
                keywords=["预算"],
            ),
        )
        self.assertIn("claim_verification", report)
        self.assertIn("arithmetic_gates", report)
        self.assertIn("assumption_grading", report)
        self.assertGreaterEqual(report["arithmetic_gates"]["passed"], 1)
        self.assertGreaterEqual(len(report["assumption_grading"]), 2)


if __name__ == "__main__":
    unittest.main()
