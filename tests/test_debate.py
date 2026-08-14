import tempfile
import unittest
from pathlib import Path
from unittest import mock

from data.storage import FileIO
from governance.config import Config
from harness.engine import CrystalEngine
from harness.processors.debate import DebateContext, DebateEngine, DebateRole, _is_reliable_output


class _FakeAI:
    api_key = "test"

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "测试回答"

    def chat_json(self, prompt, temperature=0.3, **kwargs):
        return {}


class _CaptureAuditAI:
    def __init__(self):
        self.prompt = ""

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "这是修正后的完整回答，内容完整且以句号收尾。"

    def chat_json(self, prompt, temperature=0.3, **kwargs):
        self.prompt = prompt
        return {
            "feedback_by_role": {},
            "disagreement_map": {},
            "major_conflict": False,
            "evidence_scores": {},
            "should_stop": False,
            "summary": "审计摘要",
            "round_summary": "轮次摘要",
        }


class TestDebateEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)
        (Config.DATA_ROOT / "系统日志").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "核心配置").mkdir(parents=True, exist_ok=True)
        self.engine = CrystalEngine(FileIO())
        self.debate = DebateEngine(
            _FakeAI(),
            self.engine,
            [
                {"key": "radical", "name": "激进者", "instruction": "颠覆"},
                {"key": "conservative", "name": "保守者", "instruction": "稳健"},
                {"key": "structural", "name": "结构主义者", "instruction": "类比"},
            ],
            log=lambda message, level="system": None,
        )

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_core_roles(self):
        names = [r.name for r in self.debate._core_roles()]
        self.assertIn("激进者", names)
        self.assertNotIn("百灵鸟", names)

    def test_lark_bare(self):
        answer = self.debate._run_lark_bare("测试问题")
        self.assertTrue(answer)

    def test_rumad_priority(self):
        self.debate.rumad.apply_user_preferences({"激进者": 0.4})
        ordered = self.debate.rumad.prioritize_roles(self.debate.roles)
        self.assertEqual(ordered[0].name, "激进者")

    def test_all_answers_failed(self):
        failed = [{"role": "激进者", "answer": "（激进者 发言失败: 错误：API Key 无效或已过期）"}]
        ok = [{"role": "激进者", "answer": "正常回答"}]
        self.assertTrue(DebateEngine._all_answers_failed(failed))
        self.assertFalse(DebateEngine._all_answers_failed(ok))
        self.assertFalse(DebateEngine._all_answers_failed([]))

    def test_run_raises_when_all_roles_fail(self):
        failed_answers = [
            {"role": "激进者", "answer": "（激进者 发言失败: 错误：API Key 无效或已过期）"}
        ]
        with mock.patch.object(
            DebateEngine,
            "_parallel_round0_and_round1",
            return_value=(failed_answers, "裸模型"),
        ):
            with self.assertRaises(RuntimeError):
                self.debate.run(
                    "如何设计一个多变量优化框架并评估综合策略，同时平衡长期目标与短期资源约束？",
                    mode="debate_full",
                    max_rounds=2,
                )

    def test_audit_prompt_includes_external_context(self):
        fake = _CaptureAuditAI()
        self.debate.ai = fake
        self.debate.ctx = DebateContext()
        self.debate.ctx.audit_external_context = "外部知识参考内容，包含可核验的日期、机构与数据来源。"
        self.debate._audit("测试问题", [{"role": "激进者", "answer": "回答。"}], 1)
        self.assertIn("【外部知识参考（审计判断依据）】", fake.prompt)
        self.assertIn("外部知识参考内容，包含可核验的日期", fake.prompt)


class TestSeverelyTruncatedDetection(unittest.TestCase):
    def setUp(self):
        self.debate = object.__new__(DebateEngine)

    def test_long_text_without_trailing_punctuation_is_not_truncated(self):
        text = "这是一段完整的角色发言，内容充分但没有以句号结尾"
        self.assertFalse(self.debate._is_severely_truncated(text * 20, 1500))

    def test_explicit_truncation_marker_is_truncated(self):
        text = "论述进行到这里就结束了……"
        self.assertTrue(self.debate._is_severely_truncated(text * 20, 1500))

    def test_unclosed_code_fence_is_truncated(self):
        text = "下面是代码片段：" * 20 + "```python\nprint('hi')"
        self.assertTrue(self.debate._is_severely_truncated(text, 1500))

    def test_long_output_without_punctuation_is_not_truncated(self):
        text = "接近输出上限但仍未收尾" * 200
        self.assertFalse(self.debate._is_severely_truncated(text, 2048))

    def test_complete_short_answer_is_not_truncated(self):
        self.assertFalse(self.debate._is_severely_truncated("观点明确，论证完整。", 2048))

    def test_very_short_text_is_not_truncated(self):
        self.assertFalse(self.debate._is_severely_truncated("太短", 2048))


class TestReliabilityAlarm(unittest.TestCase):
    def test_is_reliable_output_rules(self):
        self.assertTrue(_is_reliable_output("内容完整。"))
        self.assertTrue(_is_reliable_output("代码块```"))
        self.assertFalse(_is_reliable_output("内容待补充"))
        self.assertFalse(_is_reliable_output("错误：API Key 无效"))
        self.assertFalse(_is_reliable_output("内容没有正常收尾"))

    def test_review_unreliable_outputs_replaces_only_unreliable(self):
        debate = object.__new__(DebateEngine)
        debate.ctx = DebateContext()
        debate.ai = _CaptureAuditAI()
        debate.log = lambda message, level="system": None
        debate.ctx.last_round_answers = [
            {"role": "激进者", "answer": "内容包含占位TODO"},
            {"role": "保守者", "answer": "内容完整。"},
        ]
        debate.ctx.audit_external_context = "外部参考"
        debate._review_unreliable_outputs({})
        self.assertEqual(debate.ctx.last_round_answers[0]["answer"], "这是修正后的完整回答，内容完整且以句号收尾。")
        self.assertEqual(debate.ctx.last_round_answers[1]["answer"], "内容完整。")

    def test_inject_external_knowledge_feeds_audit_context(self):
        debate = object.__new__(DebateEngine)
        debate.ctx = DebateContext()
        debate.log = lambda message, level="system": None
        debate.ctx.current_question = "测试问题"
        with mock.patch.object(debate, "_fetch_external_overview", return_value="外部知识总览，包含来源链接与关键数据，供审计参考。") as _:
            debate._inject_external_knowledge({})
        self.assertEqual(debate.ctx.audit_external_context, "外部知识总览，包含来源链接与关键数据，供审计参考。")


class TestRoleSearchIntent(unittest.TestCase):
    def test_uses_jieba_and_filters_context_markers(self):
        debate = object.__new__(DebateEngine)
        role = DebateRole(key="structural", name="结构主义者", instruction="从已有晶体中寻找同构案例。")
        keywords = debate._generate_role_search_intent(
            role,
            "【本会话最近上下文】用户: 如何设计一个多变量优化框架并评估综合策略？",
        )
        self.assertNotIn("【本会话最近上下文】", keywords)
        self.assertNotIn("用户:", keywords)
        self.assertNotIn("相关信息", keywords)
        self.assertTrue(any("框架" in w or "优化" in w or "系统" in w for w in keywords))

    def test_keeps_role_specific_base_keywords(self):
        debate = object.__new__(DebateEngine)
        role = DebateRole(key="conservative", name="保守者", instruction="风险优先。")
        keywords = debate._generate_role_search_intent(role, "如何设计优化框架？")
        self.assertIn("风险", keywords)


if __name__ == "__main__":
    unittest.main()
