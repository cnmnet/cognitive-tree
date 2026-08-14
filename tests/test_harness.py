import unittest
from pathlib import Path

from core.interfaces import FlowDefinition, FlowStep
from core.registry import ProcessorRegistry
from harness.processors import register_default_processors
from harness.runner import HarnessRunner, load_flows


class TestHarness(unittest.TestCase):
    def test_education_flow_runs_in_order(self):
        registry = ProcessorRegistry()
        register_default_processors(registry)
        flows = load_flows(Path(__file__).resolve().parent.parent / "governance" / "config")
        runner = HarnessRunner(registry)
        result = runner.run(flows["education"])
        self.assertEqual(result["essay_debate"]["mode"], "education")
        self.assertEqual(result["five_versions"]["versions"], ["教师速览", "教学操作", "家长版", "学生版", "专家版"])

    def test_dependency_order(self):
        registry = ProcessorRegistry()
        register_default_processors(registry)
        flow = FlowDefinition(
            id="test",
            steps=[
                FlowStep(id="a", processor="baseline"),
                FlowStep(id="b", processor="report", depends_on=["a"]),
            ],
        )
        runner = HarnessRunner(registry)
        result = runner.run(flow)
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_cycle_detected(self):
        registry = ProcessorRegistry()
        register_default_processors(registry)
        flow = FlowDefinition(
            id="cycle",
            steps=[
                FlowStep(id="a", processor="baseline", depends_on=["b"]),
                FlowStep(id="b", processor="report", depends_on=["a"]),
            ],
        )
        runner = HarnessRunner(registry)
        with self.assertRaises(RuntimeError):
            runner.run(flow)


if __name__ == "__main__":
    unittest.main()
