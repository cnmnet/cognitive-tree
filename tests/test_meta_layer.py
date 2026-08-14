import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from evolution.meta_layer import MetaLayer
from governance.config import Config


class _FakeEngine:
    def parse_crystals(self):
        return []

    def detect_conflicts(self, method="auto"):
        return []

    def load_layer_state(self):
        return {}

    def archive_cold_crystals(self):
        return []

    def _append_change_log(self, *args, **kwargs):
        return None

    def log_evolution_event(self, *args, **kwargs):
        return None

    def _simple_similarity(self, a, b):
        return 0.9 if a == b else 0.0

    def _load_task_cards(self):
        return []

    def _save_task_cards(self, cards):
        return None

    def create_crystal(self, **kwargs):
        return True


class _FakeFiles:
    def resolve(self, key):
        return Config.DATA_ROOT / Config.PATHS.get(key, key)


class _FakeDetector:
    def detect(self, dialogue):
        return {"passed": True, "risk_level": "low", "reason": "", "records": []}


class _FakeStarlink:
    def check(self, ip):
        return {"passed": True}


class _FakeAuditor:
    def __init__(self, ai=None):
        self.ai = ai

    def audit(self, zh, en):
        return {"passed": True, "overlap_ratio": 0.9, "reason": ""}


class TestMetaLayer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        (Config.DATA_ROOT / "系统日志").mkdir(parents=True, exist_ok=True)
        providers = SimpleNamespace(
            AIPersonaDetector=_FakeDetector,
            StarlinkFingerprintDB=_FakeStarlink,
            CrossLingualAuditor=_FakeAuditor,
        )
        self.meta = MetaLayer(
            engine=_FakeEngine(),
            file_io=_FakeFiles(),
            anti_fraud_providers=providers,
        )

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_evaluation_helpers(self):
        self.assertGreater(self.meta._evaluate_importance("核心架构系统框架"), 0.5)
        self.assertEqual(self.meta._estimate_resources("短想法"), 1)

    def test_validation_gate(self):
        result = self.meta.validation_gated_self_evolution(
            {"data": 1},
            {"sources": ["a", "b", "c"], "audit_score": 0.7},
        )
        self.assertTrue(result["passed"])

    def test_saturation_detector(self):
        result = self.meta.prompt_saturation_detector(0.8)
        self.assertIn("is_saturated", result)

    def test_anti_fraud_audit(self):
        result = self.meta.run_anti_fraud_audit(
            {
                "dialogue": "我是AI助手，我的训练数据来自互联网。",
                "ip": "103.23.1.100",
                "text_zh": "知识 学习",
                "text_en": "knowledge learn",
            }
        )
        self.assertIn("overall_passed", result)
        self.assertIn("persona_detection", result)

    def test_inspiration_review(self):
        insp_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
        insp_path.parent.mkdir(parents=True, exist_ok=True)
        insp_path.write_text(
            '[{"id": "INSP-001", "content": "核心架构系统框架突破", "status": "待筛选", "created_at": "2026-01-01"}]',
            encoding="utf-8",
        )
        result = self.meta.inspiration_furnace_review()
        self.assertEqual(result["total_pending"], 1)


if __name__ == "__main__":
    unittest.main()
