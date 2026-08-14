import unittest
import tempfile
import json
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

from external.summary import summarize_role_answer
from governance.config import Config
from governance.services import load_audit_rules, load_role_ideologies, validate_audit_rules
from harness.processors.debate import (
    ROLE_BRIEF_MAX_CHARS,
    ROUND_HISTORY_MAX_CHARS,
    DebateEngine,
)


def _role(name, key):
    return SimpleNamespace(name=name, key=key, instruction="测试立场")


def _debate_instance(round_summaries=None):
    debate = DebateEngine.__new__(DebateEngine)
    debate.ctx = SimpleNamespace(round_summaries=round_summaries or {})
    debate.log = lambda message, level="system": None
    return debate


class TestDebateContextCompression(unittest.TestCase):
    def test_convergence_config_drives_constants(self):
        self.assertEqual(Config.CONVERGENCE_CONFIG["default_max_rounds"], 4)
        self.assertEqual(ROUND_HISTORY_MAX_CHARS, 15000)
        self.assertEqual(ROLE_BRIEF_MAX_CHARS, 500)

    def test_audit_rules_loader_and_validation(self):
        rules = load_audit_rules()
        self.assertEqual(rules["role_feedback_min_chars"], 200)
        self.assertEqual(rules["round_summary_min_chars"], 50)
        self.assertEqual(validate_audit_rules(rules), [])
        self.assertIn(
            "audit_max_retries 必须为正数",
            validate_audit_rules({**rules, "audit_max_retries": 0}),
        )

    def test_audit_rules_override_drives_summary_storage(self):
        tmp = tempfile.TemporaryDirectory()
        old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(tmp.name)
        cfg_dir = Config.DATA_ROOT / "核心配置"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "audit_rules.json").write_text(
            '{"round_summary_min_chars": 1}',
            encoding="utf-8",
        )
        try:
            debate = DebateEngine.__new__(DebateEngine)
            debate.ctx = SimpleNamespace(round_summaries={})
            debate.ai = mock.Mock()
            debate.ai.chat_json.return_value = {
                "feedback_by_role": {"激进者": "补强建议。" * 60},
                "disagreement_map": {},
                "evidence_scores": {"激进者": 0.8},
                "should_stop": False,
                "round_summary": "短摘要",
            }
            debate.log = lambda message, level="system": None
            debate.engine = mock.Mock()
            debate.engine.load_layer_state.return_value = {"layers": {}}
            debate.engine.parse_holes.return_value = []
            debate.engine.get_audit_status.return_value = {"available": False}
            debate._audit("问题", [{"role": "激进者", "answer": "观点"}], 1)
            self.assertIn(1, debate.ctx.round_summaries)
            self.assertEqual(debate.ctx.round_summaries[1], "短摘要")
        finally:
            Config.DATA_ROOT = old_root
            tmp.cleanup()

    def test_role_ideologies_loader_and_override(self):
        ideologies = load_role_ideologies()
        self.assertIn("radical", ideologies)
        self.assertIn("第一性原理", ideologies["radical"])
        tmp = tempfile.TemporaryDirectory()
        old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(tmp.name)
        cfg_dir = Config.DATA_ROOT / "核心配置"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "role_ideologies.json").write_text(
            json.dumps({"radical": "配置化新钢印"}, ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            debate = _debate_instance({})
            self.assertEqual(debate._get_role_ideology("radical"), "配置化新钢印")
        finally:
            Config.DATA_ROOT = old_root
            tmp.cleanup()

    def test_summarize_role_answer_keeps_conclusion_and_evidence(self):
        answer = (
            "第一段结论：采用分层迭代框架。\n\n"
            + ("无关键内容段落。" * 300)
            + "\n\n依据 [C012]，风险可控，建议执行。\n\n"
            + ("结尾填充。" * 300)
        )
        result = summarize_role_answer(answer, 800)
        self.assertLessEqual(len(result), 800)
        self.assertIn("第一段结论", result)
        self.assertIn("[C012]", result)

    def test_debate_round_layers_old_summaries_and_recent_full_text(self):
        debate = _debate_instance({1: "第一轮摘要", 2: "第二轮摘要"})
        roles = [_role("激进者", "radical"), _role("保守者", "conservative")]
        previous = [
            {"role": "激进者", "answer": "激进者反思内容"},
            {"role": "保守者", "answer": "保守者反思内容"},
        ]
        calls = []

        def fake_call(role, prompt, system, retries, max_tokens=2048):
            calls.append((role, prompt))
            return f"{role.name}第3轮发言"

        with mock.patch.object(
            DebateEngine, "_call_role_with_retry", side_effect=fake_call
        ) as call_mock, mock.patch.object(
            DebateEngine, "_get_or_create_role_external", return_value=""
        ), mock.patch.object(
            DebateEngine, "_role_system", return_value="system"
        ), mock.patch.object(
            DebateEngine,
            "_map_role_key",
            side_effect=lambda name: {"激进者": "radical", "保守者": "conservative"}.get(name, name),
        ):
            answers = debate._debate_round("问题", "", previous, {}, 3, roles)

        self.assertEqual(len(answers), 2)
        self.assertEqual(call_mock.call_count, 2)
        prompt = calls[0][1]
        self.assertIn("### 第1轮摘要\n第一轮摘要", prompt)
        self.assertIn("### 第2轮摘要\n第二轮摘要", prompt)
        self.assertIn("【最近一轮完整观点】", prompt)
        self.assertIn("激进者反思内容", prompt)
        self.assertIn("保守者反思内容", prompt)

    def test_debate_round_round2_keeps_full_text_without_summary_duplicate(self):
        debate = _debate_instance({1: "第一轮摘要"})
        roles = [_role("激进者", "radical")]
        previous = [{"role": "激进者", "answer": "第一轮激进者全文"}]
        calls = []

        def fake_call(role, prompt, system, retries, max_tokens=2048):
            calls.append((role, prompt))
            return f"{role.name}第2轮发言"

        with mock.patch.object(
            DebateEngine, "_call_role_with_retry", side_effect=fake_call
        ), mock.patch.object(
            DebateEngine, "_get_or_create_role_external", return_value=""
        ), mock.patch.object(
            DebateEngine, "_role_system", return_value="system"
        ), mock.patch.object(
            DebateEngine,
            "_map_role_key",
            side_effect=lambda name: {"激进者": "radical", "保守者": "conservative"}.get(name, name),
        ):
            debate._debate_round("问题", "", previous, {}, 2, roles)

        prompt = calls[0][1]
        self.assertIn("第一轮激进者全文", prompt)
        self.assertNotIn("### 第1轮摘要", prompt)

    def test_debate_round_compresses_overlong_history(self):
        debate = _debate_instance({})
        logs = []
        debate.log = lambda message, level="system": logs.append(message)
        roles = [
            _role("激进者", "radical"),
            _role("保守者", "conservative"),
            _role("结构主义者", "structural"),
        ]
        long_tail = "不应出现的超长尾巴标记"
        previous = [
            {
                "role": "激进者",
                "answer": "激进者开头结论。\n\n" + ("细节A。" * 1000) + long_tail + ("细节A。" * 2000),
            },
            {
                "role": "保守者",
                "answer": "保守者开头结论。\n\n" + ("细节B。" * 1000) + long_tail + ("细节B。" * 2000),
            },
            {
                "role": "结构主义者",
                "answer": "结构主义者开头结论。\n\n" + ("细节C。" * 1000) + long_tail + ("细节C。" * 2000),
            },
        ]
        calls = []

        def fake_call(role, prompt, system, retries, max_tokens=2048):
            calls.append((role, prompt))
            return f"{role.name}第2轮发言"

        with mock.patch.object(
            DebateEngine, "_call_role_with_retry", side_effect=fake_call
        ), mock.patch.object(
            DebateEngine, "_get_or_create_role_external", return_value=""
        ), mock.patch.object(
            DebateEngine, "_role_system", return_value="system"
        ), mock.patch.object(
            DebateEngine,
            "_map_role_key",
            side_effect=lambda name: {"激进者": "radical", "保守者": "conservative", "结构主义者": "structural"}.get(name, name),
        ):
            debate._debate_round("问题", "", previous, {}, 2, roles)

        prompt = calls[0][1]
        self.assertIn("激进者开头结论", prompt)
        self.assertNotIn(long_tail, prompt)
        self.assertTrue(any("[历史压缩]" in message for message in logs))

    def test_audit_compresses_long_answers(self):
        debate = DebateEngine.__new__(DebateEngine)
        debate.ctx = SimpleNamespace(round_summaries={})
        debate.ai = mock.Mock()
        debate.ai.chat_json.return_value = {
            "feedback_by_role": {"激进者": "补强建议。" * 60},
            "disagreement_map": {},
            "evidence_scores": {"激进者": 0.8},
            "should_stop": False,
            "round_summary": "本轮摘要。" * 40,
        }
        debate.log = lambda message, level="system": None
        debate.engine = mock.Mock()
        debate.engine.load_layer_state.return_value = {"layers": {}}
        debate.engine.parse_holes.return_value = []
        debate.engine.get_audit_status.return_value = {"available": False}
        long_tail = "不应出现的审计尾巴标记"
        answers = [
            {
                "role": "激进者",
                "answer": "激进者开头结论。\n\n" + ("细节。" * 2000) + "\n\n" + long_tail,
            }
        ]
        debate._audit("问题", answers, 1)
        prompt = debate.ai.chat_json.call_args[0][0]
        self.assertIn("### 激进者", prompt)
        self.assertIn("激进者开头结论", prompt)
        self.assertNotIn(long_tail, prompt)

    def test_audit_short_summary_falls_back_to_answers(self):
        debate = DebateEngine.__new__(DebateEngine)
        debate.ctx = SimpleNamespace(round_summaries={})
        debate.ai = mock.Mock()
        debate.ai.chat_json.return_value = {
            "feedback_by_role": {"激进者": "补强建议。" * 60},
            "disagreement_map": {},
            "evidence_scores": {"激进者": 0.8},
            "should_stop": False,
            "round_summary": "",
        }
        debate.log = lambda message, level="system": None
        debate.engine = mock.Mock()
        debate.engine.load_layer_state.return_value = {"layers": {}}
        debate.engine.parse_holes.return_value = []
        debate.engine.get_audit_status.return_value = {"available": False}
        answers = [
            {"role": "激进者", "answer": "激进者提出分层迭代方案。理由充分。"},
            {"role": "保守者", "answer": "保守者强调风险优先。需要回退机制。"},
        ]
        debate._audit("问题", answers, 1)
        self.assertIn(1, debate.ctx.round_summaries)
        summary = debate.ctx.round_summaries[1]
        self.assertIn("激进者", summary)
        self.assertIn("保守者", summary)
        self.assertGreater(len(summary), 10)

    def test_reflection_round_uses_summary_and_own_speech_only(self):
        debate = _debate_instance({2: "第二轮摘要"})
        roles = [_role("激进者", "radical"), _role("保守者", "conservative")]
        previous_answers = [
            {"role": "激进者", "answer": "激进者第二轮发言"},
            {"role": "保守者", "answer": "保守者第二轮发言"},
        ]
        calls = []

        def fake_call(role, prompt, system, retries, max_tokens=2048):
            calls.append((role, prompt))
            return f"{role.name}反思"

        with mock.patch.object(
            DebateEngine, "_call_role_with_retry", side_effect=fake_call
        ), mock.patch.object(
            DebateEngine, "_get_or_create_role_external", return_value=""
        ), mock.patch.object(
            DebateEngine, "_role_system", return_value="system"
        ), mock.patch.object(
            DebateEngine,
            "_map_role_key",
            side_effect=lambda name: {"激进者": "radical", "保守者": "conservative"}.get(name, name),
        ):
            debate._reflection_round(
                "问题", "", previous_answers, {}, roles, round_num=2
            )

        prompts_by_role = {role.name: prompt for role, prompt in calls}
        radical_prompt = prompts_by_role["激进者"]
        self.assertIn("【第 2 轮摘要】\n第二轮摘要", radical_prompt)
        self.assertIn("【你上一轮发言】\n激进者第二轮发言", radical_prompt)
        self.assertNotIn("保守者第二轮发言", radical_prompt)

    def test_reflection_round_falls_back_to_full_text(self):
        debate = _debate_instance({})
        roles = [_role("激进者", "radical")]
        previous_answers = [{"role": "保守者", "answer": "保守者发言全文"}]
        calls = []

        def fake_call(role, prompt, system, retries, max_tokens=2048):
            calls.append((role, prompt))
            return f"{role.name}反思"

        with mock.patch.object(
            DebateEngine, "_call_role_with_retry", side_effect=fake_call
        ), mock.patch.object(
            DebateEngine, "_get_or_create_role_external", return_value=""
        ), mock.patch.object(
            DebateEngine, "_role_system", return_value="system"
        ), mock.patch.object(
            DebateEngine,
            "_map_role_key",
            side_effect=lambda name: {"激进者": "radical", "保守者": "conservative"}.get(name, name),
        ):
            debate._reflection_round(
                "问题", "", previous_answers, {}, roles, round_num=2
            )

        prompt = calls[0][1]
        self.assertIn("【保守者】\n保守者发言全文", prompt)

    def test_role_system_injects_rumad_focus(self):
        debate = _debate_instance({})
        debate.ctx.rumad_focus = ("激进者", "保守者")
        system = debate._role_system(
            _role("保守者", "conservative"),
            "",
            round_num=3,
        )
        self.assertIn("RUMAD 拓扑指令", system)
        self.assertIn("保守者 必须直接回应 激进者", system)


if __name__ == "__main__":
    unittest.main()
