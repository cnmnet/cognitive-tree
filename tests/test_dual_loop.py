import tempfile
import unittest
from pathlib import Path

from data.storage import FileIO
from evolution.dual_loop import DualLoopRunner
from evolution.operators import OperatorExecutor, build_patch
from governance.config import Config
from harness.engine import CrystalEngine


class TestDualLoop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        (Config.DATA_ROOT / "系统日志").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "核心配置").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "晶体数据").mkdir(parents=True, exist_ok=True)
        self.engine = CrystalEngine(FileIO())
        self.engine.create_crystal("C001", "机器学习与深度学习", links=[], source="test")
        self.engine.create_crystal("C002", "机器学习与深度学习训练方法", links=[], source="test")
        self.engine.create_crystal("C003", "物流运输优化", links=[], source="test")

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_operator_executor_merge_and_rollback(self):
        executor = OperatorExecutor(self.engine)
        result = executor.apply(build_patch("CRYSTAL_MERGE", "C001", {"a": "C001", "b": "C002"}))
        self.assertTrue(result["ok"], result)
        crystals = {c.id: c for c in self.engine.parse_crystals()}
        self.assertNotIn("C002", crystals)
        self.assertIn("训练方法", crystals["C001"].content, crystals["C001"].content)
        self.assertTrue(executor.rollback(result["record"]))
        crystals = {c.id: c for c in self.engine.parse_crystals()}
        self.assertIn("C002", crystals)
        self.assertEqual(crystals["C001"].content, "机器学习与深度学习")

    def test_operator_executor_graft_and_prune(self):
        executor = OperatorExecutor(self.engine)
        graft_result = executor.apply(build_patch("CRYSTAL_ADD", "new", {"content": "新认知晶体"}))
        self.assertTrue(graft_result["ok"], graft_result)
        new_id = graft_result["record"]["target"]
        self.assertTrue(any(c.id == new_id for c in self.engine.parse_crystals()))
        prune_result = executor.apply(build_patch("CRYSTAL_DELETE", new_id, {}))
        self.assertTrue(prune_result["ok"], prune_result)
        self.assertFalse(any(c.id == new_id for c in self.engine.parse_crystals()))
        self.assertTrue(executor.rollback(prune_result["record"]))
        self.assertTrue(any(c.id == new_id for c in self.engine.parse_crystals()))

    def test_dual_loop_runs_and_merges_conflicts(self):
        runner = DualLoopRunner(self.engine)
        report = runner.run_once(max_merges=1, max_grafts=0)
        self.assertIn("executed", report)
        self.assertIn("verify", report)
        if report["executed"] > 0:
            self.assertFalse(any(c.id == "C002" for c in self.engine.parse_crystals()))


if __name__ == "__main__":
    unittest.main()
