import unittest

from core.interfaces import FlowDefinition
from core.models import Crystal, Hole, Report


class TestModels(unittest.TestCase):
    def test_crystal_and_hole(self):
        crystal = Crystal(id="C001", content="示例晶体")
        hole = Hole(id="H001", content="示例孔洞")
        self.assertEqual(crystal.layer.value, 2)
        self.assertEqual(hole.urgency, 0.5)

    def test_report(self):
        report = Report(title="报告", sections={"结论": "通过"})
        self.assertIn("结论", report.sections)

    def test_flow_definition_from_dict(self):
        flow = FlowDefinition.from_dict(
            "demo",
            {
                "steps": [
                    {"id": "a", "processor": "x"},
                    {"id": "b", "processor": "y", "depends_on": ["a"]},
                ]
            },
        )
        self.assertEqual(flow.id, "demo")
        self.assertEqual(flow.steps[1].depends_on, ["a"])


if __name__ == "__main__":
    unittest.main()
