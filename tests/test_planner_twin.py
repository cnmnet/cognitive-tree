import tempfile
import unittest
from pathlib import Path

from data.storage import FileIO
from external.fetcher import ExternalFetcher
from governance.config import Config
from harness.engine import CrystalEngine
from evolution.meta_search import MetaSearchEngine
from harness.processors.planner import BaselineRunner, DailyPlanner
from harness.twin_workbench import TwinProfile, TwinWorkbench


class _FakeAI:
    api_key = "test"

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "测试回答" * 50

    def chat_json(self, prompt, temperature=0.3, **kwargs):
        return {}


class TestPlannerTwin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        (Config.DATA_ROOT / "系统日志").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "核心配置").mkdir(parents=True, exist_ok=True)
        self.engine = CrystalEngine(FileIO())
        self.ai = _FakeAI()

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_instantiation(self):
        roles = [{"key": "radical", "name": "激进者", "instruction": "颠覆"}]
        BaselineRunner(self.engine, self.ai, roles)
        MetaSearchEngine(self.engine, self.ai)
        DailyPlanner(
            self.engine,
            self.ai,
            ExternalFetcher(file_io=FileIO),
            lambda message, level="system": None,
            lambda message: None,
        )
        TwinWorkbench(self.engine, self.ai)

    def test_twin_profile_defaults(self):
        profile = TwinProfile(name="测试替身", role="决策替身")
        self.assertEqual(profile.name, "测试替身")


if __name__ == "__main__":
    unittest.main()
