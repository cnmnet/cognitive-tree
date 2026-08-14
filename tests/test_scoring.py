import unittest

from core.scoring import score_line, score_payload, score_report, score_summary


class TestScoring(unittest.TestCase):
    def test_score_report_returns_eight_dimensions(self):
        text = (
            "因为证据不足，所以需要先验证假设。第一步建立诊断机制，"
            "第二步执行止损，第三步复盘。风险清单与路线图如下。"
        )
        scores = score_report(text)
        self.assertEqual(len(scores), 8)
        self.assertEqual(
            list(scores.keys()),
            [
                "argument_depth",
                "evidence_quality",
                "logic_rigor",
                "perspective_diversity",
                "innovation_insight",
                "structure_organization",
                "readability",
                "practical_value",
            ],
        )
        self.assertTrue(all(0 <= v <= 100 for v in scores.values()))

    def test_score_line_contains_all_labels(self):
        line = score_line("建议分三步执行，并识别风险与止损方案。")
        self.assertIn("【回答质量评分】", line)
        self.assertIn("论证深度", line)
        self.assertIn("综合总分", line)

    def test_score_payload_matches_summary(self):
        text = "因为问题复杂，所以需要分步骤处理，并设置止损与预算。"
        payload = score_payload(text)
        self.assertEqual(payload["total"], score_summary(payload["scores"]))


if __name__ == "__main__":
    unittest.main()
