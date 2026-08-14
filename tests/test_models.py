import unittest

from core.models import CognitiveFingerprint, Crystal, Hole, Report


class TestModels(unittest.TestCase):
    def test_crystal_and_hole(self):
        crystal = Crystal(id="C001", content="示例晶体")
        hole = Hole(id="H001", content="示例孔洞")
        self.assertEqual(crystal.layer.value, 2)
        self.assertEqual(hole.urgency, 0.5)

    def test_fingerprint_roundtrip(self):
        fp = CognitiveFingerprint(
            risk_tolerance=0.8,
            preferred_role="radical",
            language_style={"wenbai_ratio": "wen"},
        )
        restored = CognitiveFingerprint.from_dict(fp.to_dict())
        self.assertEqual(restored.risk_tolerance, 0.8)
        self.assertEqual(restored.preferred_role, "radical")
        self.assertEqual(restored.language_style["wenbai_ratio"], "wen")

    def test_report(self):
        report = Report(title="报告", sections={"结论": "通过"})
        self.assertIn("结论", report.sections)


if __name__ == "__main__":
    unittest.main()
