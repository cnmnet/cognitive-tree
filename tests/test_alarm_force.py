import tempfile
import unittest
from pathlib import Path

from governance.config import Config
from harness.alarm import AlarmMonitor
from harness.force_explorer import ForceExplorer
from harness.processors.debate import compute_bias_amplification


class _Hole:
    def __init__(self, hole_id, content, urgency):
        self.id = hole_id
        self.content = content
        self.urgency = urgency
        self.links = []


class _Engine:
    def parse_holes(self):
        return [_Hole("H001", "高紧迫孔洞", 0.9), _Hole("H002", "普通孔洞", 0.5)]

    def load_hole_progress(self):
        return {"H001": 0.2}

    def parse_crystals(self):
        return []

    def rank_crystals(self, query, crystals, top_k=5):
        return []

    def create_crystal(self, **kwargs):
        return True

    def log_evolution_event(self, *args, **kwargs):
        return None


class TestAlarmMonitor(unittest.TestCase):
    def test_config_has_eight_rules(self):
        self.assertEqual(len(Config.ALARM_RULES), 8)

    def test_knowledge_poverty(self):
        monitor = AlarmMonitor()
        alarms = monitor.check({"crystal_reference_rate": 0.2})
        self.assertTrue(any(a["rule"] == "knowledge_poverty" for a in alarms))

    def test_information_starvation(self):
        monitor = AlarmMonitor()
        alarms = []
        for _ in range(3):
            alarms = monitor.check({"external_has_new": False})
        self.assertTrue(any(a["rule"] == "information_starvation" for a in alarms))

    def test_evidence_strength(self):
        monitor = AlarmMonitor()
        alarms = monitor.check({"evidence_strength": 0.1})
        self.assertTrue(any(a["rule"] == "evidence_strength" for a in alarms))

    def test_logic_consistency(self):
        monitor = AlarmMonitor()
        alarms = monitor.check({"logic_consistency": 0.2})
        self.assertTrue(any(a["rule"] == "logic_consistency" for a in alarms))

    def test_overreach(self):
        monitor = AlarmMonitor()
        alarms = monitor.check({"overreach_score": 0.5})
        self.assertTrue(any(a["rule"] == "overreach" for a in alarms))

    def test_output_reliability(self):
        monitor = AlarmMonitor()
        alarms = monitor.check({"reliability_score": 0.4})
        self.assertTrue(any(a["rule"] == "output_reliability" for a in alarms))

    def test_bias_inflation(self):
        monitor = AlarmMonitor()
        alarms = monitor.check({"bias_amplification": 0.6})
        self.assertTrue(any(a["rule"] == "bias_inflation" for a in alarms))

    def test_thought_stagnation(self):
        monitor = AlarmMonitor()
        alarms = []
        for _ in range(3):
            alarms = monitor.check({"jaccard_similarity": 0.9})
        self.assertTrue(any(a["rule"] == "thought_stagnation" for a in alarms))

    def test_compute_bias_amplification(self):
        answers = [
            {"answer": "毫无疑问必须执行A"},
            {"answer": "可以考虑B"},
        ]
        self.assertAlmostEqual(compute_bias_amplification(answers), 0.5)

    def test_all_actions_dispatch(self):
        calls = []

        class _Debate:
            def _inject_external_knowledge(self, alarm):
                calls.append("inject_external")

            def _review_unreliable_outputs(self, alarm):
                calls.append("review_output")

            def _inject_perspective(self, alarm):
                calls.append("inject_perspective")

            def _trigger_search(self, alarm):
                calls.append("trigger_search")

        debate = _Debate()
        scenarios = [
            ("knowledge_poverty", {"crystal_reference_rate": 0.1}, "inject_external"),
            ("bias_inflation", {"bias_amplification": 0.9}, "inject_perspective"),
            ("information_starvation", {"external_has_new": False}, "trigger_search"),
            ("thought_stagnation", {"jaccard_similarity": 0.9}, "inject_perspective"),
            ("evidence_strength", {"evidence_strength": 0.1}, "trigger_search"),
            ("logic_consistency", {"logic_consistency": 0.2}, "inject_perspective"),
            ("overreach", {"overreach_score": 0.9}, "inject_perspective"),
            ("output_reliability", {"reliability_score": 0.2}, "review_output"),
        ]
        for rule, metrics, _expected in scenarios:
            monitor = AlarmMonitor()
            alarms = []
            for _ in range(3):
                alarms = monitor.check(metrics)
            alarm = next(a for a in alarms if a["rule"] == rule)
            monitor.handle_alarm(alarm, debate)
        self.assertEqual(
            set(calls),
            {"inject_external", "review_output", "inject_perspective", "trigger_search"},
        )


class TestForceExplorer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        self.explorer = ForceExplorer(
            engine=_Engine(),
            log_callback=lambda msg, level="system": None,
        )

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_escalation(self):
        escalated = self.explorer.check_holes_for_escalation(threshold_days=7)
        self.assertTrue(any(e["hole_id"] == "H001" for e in escalated))

    def test_status(self):
        status = self.explorer.get_exploration_status()
        self.assertEqual(status["total_holes"], 2)


if __name__ == "__main__":
    unittest.main()
