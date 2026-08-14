import tempfile
import unittest
from pathlib import Path

from data.storage import FileIO
from governance.config import Config
from harness.engine import CrystalEngine


class TestCrystalEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        (Config.DATA_ROOT / "系统日志").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "核心配置").mkdir(parents=True, exist_ok=True)
        self.engine = CrystalEngine(FileIO())

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_classify_question(self):
        categories = self.engine._classify_question("如何优化系统架构并提升性能？")
        self.assertIsInstance(categories, list)
        self.assertTrue(categories)

    def test_crystal_crud(self):
        self.assertTrue(
            self.engine.create_crystal(
                crystal_id="C001",
                content="认知原则：决策前必须引用晶体",
                links=[],
                source="test",
            )
        )
        crystals = self.engine.parse_crystals()
        self.assertTrue(any(c.id == "C001" for c in crystals))
        self.assertTrue(self.engine.delete_crystal("C001"))

    def test_similarity_and_ranking(self):
        self.assertGreater(
            self.engine._simple_similarity("机器学习模型", "机器学习模型训练"),
            0,
        )
        from core.models import Crystal

        crystals = [
            Crystal(id="C001", content="机器学习与深度学习", links=[]),
            Crystal(id="C002", content="物流运输优化", links=[]),
        ]
        ranked = self.engine.rank_crystals("机器学习", crystals, top_k=2)
        self.assertEqual(ranked[0][1].id, "C001")

    def test_hebbian_and_vote(self):
        self.engine.update_hebbian_weights(["C001", "C002"], task_type="tech", score=0.8)
        self.assertGreater(self.engine.get_hebbian_boost("C001", task_type="tech"), 0)
        self.engine.vote_role("radical", True)
        self.assertGreater(self.engine.hebbian_weights.get("vote_radical", 0.5), 0.5)

    def test_hebbian_adopt_reward(self):
        self.engine.record_hebbian_reward(
            "adopt",
            crystal_ids=["C001", "C002"],
            role_keys=["radical"],
            task_type="tech",
        )
        self.assertGreater(self.engine.hebbian_weights.get("vote_radical", 0.5), 0.5)
        task_keys = [k for k in self.engine.hebbian_weights if k.startswith("task_") and "C001" in k]
        self.assertTrue(task_keys)
        self.assertTrue(any(self.engine.hebbian_weights[k] > 0.0 for k in task_keys))
        self.assertGreater(self.engine.get_hebbian_boost("C001", task_type="tech"), 0)

    def test_hebbian_activity_reward(self):
        self.engine.record_hebbian_reward("activity", role_keys=["lark"])
        self.assertEqual(self.engine.hebbian_weights.get("activity_lark", 0), 1)
        self.assertGreater(self.engine.hebbian_weights.get("vote_lark", 0.5), 0.5)

    def test_hebbian_decay(self):
        self.engine.hebbian_weights["vote_radical"] = 0.9
        from datetime import datetime, timedelta

        self.engine.hebbian_weights["_last_updated"] = (datetime.now() - timedelta(days=10)).isoformat()
        self.engine._apply_hebbian_decay()
        value = self.engine.hebbian_weights["vote_radical"]
        self.assertGreater(value, 0.5)
        self.assertLess(value, 0.9)

    def test_hebbian_stats(self):
        self.engine.record_hebbian_reward("activity", role_keys=["structural"])
        stats = self.engine.get_hebbian_stats()
        self.assertGreaterEqual(stats["event_count"], 1)
        self.assertEqual(stats["activity"].get("activity_structural"), 1)

    def test_layer_state(self):
        self.engine.update_crystal_access_time("C001")
        state = self.engine.load_layer_state()
        self.assertIn("last_accessed", state)


if __name__ == "__main__":
    unittest.main()
