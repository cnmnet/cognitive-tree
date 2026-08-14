import builtins
import tempfile
import unittest
from pathlib import Path

from core.fingerprint import FingerprintExtractor
from core.models import CognitiveFingerprint
from data.vector_store import VectorStore
from governance.config import Config
from harness.audit import LayerAuditService, LayerContribution


class _FakeFiles:
    def read_fingerprint(self):
        return {"fingerprint": {"evolution_log": [], "total_interactions": 0}}

    def write_fingerprint(self, data):
        pass


class TestFingerprintExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = FingerprintExtractor(engine=None, file_io=_FakeFiles())

    def test_analyze_keywords(self):
        risk, innovation = self.extractor._analyze_keywords([("user", "风险 成本 失败 安全")])
        self.assertGreater(risk, innovation)

    def test_pure_helpers(self):
        self.assertGreater(self.extractor._smooth_update(0.5, 0.9, 0.3), 0.6)
        merged = self.extractor._merge_role_history({"激进者": 1}, {"激进者": 2, "保守者": 1})
        self.assertEqual(merged["激进者"], 3)

    def test_operators(self):
        fp = CognitiveFingerprint(
            reasoning_style="deductive",
            analogy_preference="analogy",
            output_style="conclusion_first",
        )
        self.assertIn("演绎", self.extractor.get_cognitive_operators(fp))


class TestLayerAuditService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        self.service = LayerAuditService(engine=None, file_io=_FakeFiles())

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_health_score_and_recommendations(self):
        layers = [
            LayerContribution("L1", 20, 50.0, "stable", 0.0, 0.5, ""),
            LayerContribution("L2", 15, 30.0, "stable", 0.0, 0.5, ""),
            LayerContribution("L3", 10, 20.0, "stable", 0.0, 0.5, ""),
        ]
        score = self.service._calculate_health_score(
            layers,
            {"CrystalEngine": True, "MetaLayer": True, "CheapGate": True},
            8.0,
        )
        self.assertGreater(score, 0)
        recs = self.service._generate_recommendations(layers, {"CrystalEngine": True}, 9.0)
        self.assertTrue(recs)

    def test_should_run_audit(self):
        self.assertTrue(self.service._should_run_audit())


class TestVectorStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_degraded_store(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "chromadb" or name.startswith("chromadb."):
                raise ImportError("chromadb disabled for test")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            store = VectorStore(file_io=None)
            self.assertEqual(store.count(), 0)
            self.assertEqual(store.add_crystals([]), 0)
        finally:
            builtins.__import__ = real_import


if __name__ == "__main__":
    unittest.main()
