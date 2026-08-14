import tempfile
import unittest
from pathlib import Path

from governance.config import Config
from governance.prompt_templates import PromptTemplateManager
from harness.assurance.anti_fraud import AIPersonaDetector, CrossLingualAuditor, StarlinkFingerprintDB


class TestPromptTemplates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        self.manager = PromptTemplateManager(file_io=None)

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_default_templates(self):
        template = self.manager.get_template("radical")
        self.assertIsNotNone(template)
        self.assertIn("激进者", template.system_prompt)

    def test_update_and_rollback(self):
        template = self.manager.get_template("radical")
        old_version = template.version
        self.assertTrue(self.manager.update_template("radical", system_prompt="新的激进者提示"))
        self.assertEqual(template.version, old_version + 1)
        self.assertFalse(self.manager.rollback("radical", 1))


class TestAntiFraud(unittest.TestCase):
    def test_persona_detector(self):
        result = AIPersonaDetector().detect("我是AI助手，我的训练数据来自互联网。")
        self.assertIn("risk_score", result)
        self.assertGreaterEqual(result["risk_score"], 0)

    def test_starlink_db(self):
        db = StarlinkFingerprintDB()
        self.assertFalse(db.check("103.23.1.100")["passed"])
        self.assertTrue(db.check("8.8.8.8")["passed"])

    def test_cross_lingual_auditor(self):
        auditor = CrossLingualAuditor()
        self.assertFalse(auditor.audit("", "")["passed"])
        result = auditor.audit("知识 学习", "knowledge learn")
        self.assertIn("is_consistent", result)


if __name__ == "__main__":
    unittest.main()
