import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from data.storage import FileIO
from governance.config import Config
from harness.engine import CrystalEngine
from harness.processors.debate import DebateEngine
from harness.processors.planner import BaselineRunner


def synthetic_result(question, **kwargs):
    return {
        "rounds": [
            {
                "round": 1,
                "answers": [
                    {"role": "激进者", "answer": "[C001] 机制设计。"},
                    {"role": "保守者", "answer": "[H001] 风险控制。"},
                ],
                "audit": {
                    "feedback_by_role": {"激进者": "补充证据。", "保守者": "给出指标。"},
                    "disagreement_map": {"risk": True, "cost": False},
                    "evidence_scores": {"激进者": 0.7, "保守者": 0.5},
                },
            },
            {
                "round": 2,
                "answers": [
                    {"role": "激进者", "answer": "[C001] 分三步执行并识别风险。"},
                    {"role": "保守者", "answer": "[H001] 建议设置止损与时间节点。"},
                ],
                "audit": {
                    "feedback_by_role": {"激进者": "可行。", "保守者": "可以执行。"},
                    "disagreement_map": {"risk": True, "cost": True},
                    "evidence_scores": {"激进者": 0.8, "保守者": 0.6},
                },
            },
        ],
        "final": {
            "one_sentence_conclusion": "用诊断机制打破惯性。",
            "student_friendly_answer": "建议先诊断、再分步骤执行，并识别风险。",
            "teacher_detail": "包含可执行步骤，并列出风险边界与止损机制。",
        },
    }


class TestBaselineRunnerTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        (Config.DATA_ROOT / "系统日志").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "核心配置").mkdir(parents=True, exist_ok=True)
        self.engine = CrystalEngine(FileIO())
        self.ai = mock.Mock()
        self.ai.api_key = ""

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_question_limit_and_output_path(self):
        runner = BaselineRunner(self.engine, self.ai, [{"key": "radical", "name": "激进者", "instruction": "x"}])
        output = Config.DATA_ROOT / "docs" / "debate_baseline.json"
        with mock.patch.object(DebateEngine, "run", side_effect=synthetic_result):
            data = runner.run(max_rounds=2, question_limit=1, output_path=output)

        self.assertEqual(data["total_questions"], 1)
        self.assertTrue(output.exists())
        loaded = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(loaded["summary"]["total_valid"], 1)
        self.assertEqual(loaded["summary"]["total_errors"], 0)
        detail = loaded["details"][0]
        self.assertTrue(detail["has_risks"])
        self.assertTrue(detail["has_executable_actions"])
        self.assertGreater(detail["crystal_reference_rate"], 0)

    def test_empty_result_summary_marks_error(self):
        runner = BaselineRunner(self.engine, self.ai, [{"key": "radical", "name": "激进者", "instruction": "x"}])
        output = Config.DATA_ROOT / "docs" / "debate_baseline_empty.json"
        with mock.patch.object(DebateEngine, "run", side_effect=RuntimeError("all roles failed")):
            data = runner.run(max_rounds=1, question_limit=1, output_path=output)
        self.assertEqual(data["summary"], {"error": "无有效结果"})
        self.assertEqual(data["details"][0]["error"], "all roles failed")

    def test_raw_final_from_final_schema(self):
        runner = BaselineRunner(self.engine, self.ai, [{"key": "radical", "name": "激进者", "instruction": "x"}])
        result = synthetic_result("测试问题")
        result["final"] = {}
        result["final_schema"] = {
            "board_version": "老板版决策摘要",
            "employee_version": "员工版SOP",
            "novice_version": "新人版通俗解释",
            "expert_version": "专家版详细分析",
        }
        metrics = runner._extract_metrics("测试问题", result)
        self.assertTrue(metrics["raw_final"])
        self.assertIn(
            "老板版决策摘要",
            metrics["raw_final"]["rigid_core"]["decision_summary"],
        )
        self.assertIn(
            "新人版通俗解释",
            metrics["raw_final"]["student_friendly_answer"],
        )


if __name__ == "__main__":
    unittest.main()
