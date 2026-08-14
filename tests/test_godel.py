import tempfile
import unittest
from pathlib import Path

from evolution.godel import GödelAgent
from governance.config import Config
from governance.prompt_templates import PromptTemplateManager


class _FakeEngine:
    def parse_crystals(self):
        return []

    def create_crystal(self, **kwargs):
        return True

    def log_evolution_event(self, *args, **kwargs):
        return None


class _FakeAI:
    api_key = "test"

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "[C001] 引用测试答案。"


class TestGodelAgent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        self.agent = GödelAgent(
            engine=_FakeEngine(),
            ai_client=_FakeAI(),
            template_manager=PromptTemplateManager(file_io=None),
        )

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_jaccard(self):
        self.assertGreater(self.agent._compute_jaccard("认知晶体树 决策", "认知晶体树 决策 系统"), 0)

    def test_instructions(self):
        self.assertIn("减少偏见", self.agent._reduce_bias_instruction("测试提示"))
        self.assertIn("晶体引用", self.agent._strengthen_crystal_instruction("测试提示"))
        improved = self.agent._get_default_improvement("radical", "当前提示")
        self.assertEqual(improved["type"], "enhance_disruptive_thinking")

    def test_validate_candidate(self):
        candidate = {
            "content": "认知原则框架：决策前必须引用晶体",
            "links": [],
        }
        result = self.agent.validate_crystal_candidate(candidate)
        self.assertTrue(result["passed"])

    def test_status(self):
        status = self.agent.get_evolution_status()
        self.assertEqual(status["total_evolutions"], 0)


if __name__ == "__main__":
    unittest.main()
