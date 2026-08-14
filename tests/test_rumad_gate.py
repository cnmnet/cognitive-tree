import unittest

from harness.gate import CheapGate
from harness.rumad import RUMADController


class _Role:
    def __init__(self, name):
        self.name = name


class TestRUMAD(unittest.TestCase):
    def test_preferences_and_priority(self):
        rumad = RUMADController(["激进者", "保守者", "结构主义者"])
        rumad.apply_user_preferences({"激进者": 0.4})
        roles = [_Role("保守者"), _Role("激进者"), _Role("结构主义者")]
        ordered = rumad.prioritize_roles(roles)
        self.assertEqual(ordered[0].name, "激进者")

    def test_state_key_and_reward(self):
        rumad = RUMADController(["激进者", "保守者"])
        key = rumad._get_state_key([0.1, 0.9], 2, 0.5)
        self.assertIn("L", key)
        answers = [{"role": "激进者", "answer": "颠覆创新突破"}]
        reward = rumad.compute_reward(answers, answers, {}, {})
        self.assertGreaterEqual(reward, -1.0)
        self.assertLessEqual(reward, 1.0)

    def test_warmup_select_action(self):
        rumad = RUMADController(["激进者", "保守者"])
        actions = [("激进者", "保守者"), ("保守者", "激进者")]
        action = rumad.select_action("state", actions, 2)
        self.assertIn(action, actions)

    def test_set_enabled(self):
        rumad = RUMADController(["激进者", "保守者"])
        rumad.set_enabled(False)
        self.assertFalse(rumad.enabled)
        rumad.set_enabled(True)
        self.assertTrue(rumad.enabled)


class TestCheapGate(unittest.TestCase):
    def setUp(self):
        self.gate = CheapGate(
            engine=None,
            file_io=None,
            log_callback=lambda msg, level="system": None,
        )

    def test_sanitize(self):
        corrected, msg = self.gate._sanitize_user_input("预算 5000 元")
        self.assertTrue(msg)
        self.assertIn("10万", corrected)

    def test_check_simple(self):
        result = self.gate.check("你好", [])
        self.assertEqual(result["complexity"], "simple")
        self.assertTrue(result["skip_llm"])

    def test_check_high(self):
        question = "如何设计一个多变量优化框架并评估综合策略，同时平衡长期目标与短期资源约束？"
        result = self.gate.check(question, [])
        self.assertEqual(result["complexity"], "high")

    def test_adjust_search_counter(self):
        self.gate.adjust_search_counter(1)
        self.assertEqual(self.gate._search_counter, 1)
        self.gate.adjust_search_counter(0)
        self.assertEqual(self.gate._search_counter, 0)


if __name__ == "__main__":
    unittest.main()
