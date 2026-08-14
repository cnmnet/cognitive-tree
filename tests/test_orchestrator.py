import unittest

from harness.orchestrator import (
    FinalOutputSchema,
    OutputOrchestrator,
    SynapseStore,
    compute_dashboard_stats,
)


class _FakeAI:
    api_key = "test"

    def chat(self, prompt, system=None, temperature=0.5, **kwargs):
        return "测试回答"

    def chat_json(self, prompt, temperature=0.3, **kwargs):
        return {
            "role_scorecard": [],
            "final_verdict": "采纳测试",
            "rejected_items": [],
        }

    def _call_api(self, messages, temperature=0.7, response_format=None,
                  stream=False, callback=None, max_tokens=None):
        return (
            '{"role_scorecard": [{"role": "激进者", "core_view": "测试", '
            '"strength": 8, "novelty": 9, "feasibility": 4, "evidence_quality": 6, '
            '"relevance": 7, "alignment": 5, "activation": 8, "contribution_percent": 15, '
            '"status": "rejected", "brief_reason": "可落地不足", "system_basis": "[C051]"}], '
            '"final_verdict": "采纳测试", "rejected_items": []}'
        )


class _FakeEngine:
    def get_role_synapses(self, role_key):
        return {"C001": 0.5}

    def update_role_synapse(self, role_key, crystal_id, delta):
        return 0.6

    def _update_role_win_loss(self, role_key, win):
        return None


class _AnnexAI(_FakeAI):
    def chat_json(self, prompt, temperature=0.3, **kwargs):
        if "决策编排师" in prompt:
            return {
                "final_decision": "主攻B，A作为赋能工具",
                "resource_allocation": {"ratio": "70/30", "detail": "B为主攻方向"},
                "budget": [{"item": "B线", "amount": "700万", "note": "主攻"}],
                "timeline": [{"phase": "0-3个月", "actions": "试点", "milestone": "验收"}],
                "stop_loss": [{"metric": "毛利率", "threshold": "15%", "action": "止损"}],
                "risk_control": [{"risk": "合规", "level": "P0", "mitigation": "法务"}],
                "acceptance_criteria": ["首期验收通过"],
                "owners": [{"role": "项目负责人", "responsibility": "统筹"}],
            }
        return super().chat_json(prompt, temperature=temperature, **kwargs)


class _RetryAnnexAI(_FakeAI):
    def __init__(self):
        self.annex_calls = 0

    def chat_json(self, prompt, temperature=0.3, **kwargs):
        if "决策编排师" not in prompt:
            return super().chat_json(prompt, temperature=temperature, **kwargs)
        self.annex_calls += 1
        if self.annex_calls == 1:
            return {
                "final_decision": "双轨渐进",
                "resource_allocation": {"ratio": "60/40", "total": "800万元", "detail": "B主A辅"},
                "budget": [
                    {"item": "B专业渠道", "amount": "400万元", "note": "主攻"},
                    {"item": "A直播电商", "amount": "350万元", "note": "辅助"},
                ],
            }
        return {
            "final_decision": "双轨渐进",
            "resource_allocation": {"ratio": "60/40", "total": "800万元", "detail": "B主A辅"},
            "budget": [
                {"item": "B专业渠道", "amount": "480万元", "note": "主攻"},
                {"item": "A直播电商", "amount": "320万元", "note": "辅助"},
            ],
        }


class TestOrchestrator(unittest.TestCase):
    def test_dashboard_stats(self):
        stats = compute_dashboard_stats({"final_verdict": "采纳"})
        self.assertIsInstance(stats, dict)

    def test_schema(self):
        schema = FinalOutputSchema()
        self.assertEqual(schema.judge_final_verdict, "")
        self.assertIn("role_scorecard", schema.judge_audit)

    def test_synapse_store(self):
        engine = _FakeEngine()
        self.assertEqual(SynapseStore.get_synapse(engine, "radical", "C001"), 0.5)
        self.assertEqual(SynapseStore.update_synapse(engine, "radical", "C001", 0.1), 0.6)

    def test_decision_annex_from_ai(self):
        orch = OutputOrchestrator(_AnnexAI(), _FakeEngine())
        atomic = {"role_contributions": {"激进者": {"viewpoints": ["颠覆方案"]}}}
        judge = {"final_verdict": "采纳B", "rejected_items": []}
        annex = orch._build_decision_annex("测试问题", atomic, judge)
        self.assertEqual(annex["final_decision"], "主攻B，A作为赋能工具")
        self.assertEqual(annex["resource_allocation"]["ratio"], "70/30")
        self.assertEqual(annex["budget"][0]["amount"], "700万")

    def test_decision_annex_fallback(self):
        orch = OutputOrchestrator(_FakeAI(), _FakeEngine())
        atomic = {"role_contributions": {}}
        judge = {"final_verdict": "采纳B", "rejected_items": []}
        annex = orch._build_decision_annex("测试问题", atomic, judge)
        self.assertEqual(annex["final_decision"], "采纳B")
        self.assertEqual(annex["budget"], [])

    def test_decision_annex_retries_on_budget_mismatch(self):
        ai = _RetryAnnexAI()
        orch = OutputOrchestrator(ai, _FakeEngine())
        atomic = {"role_contributions": {"激进者": {"viewpoints": ["直播优先"]}}}
        judge = {"final_verdict": "双轨渐进", "rejected_items": []}
        annex = orch._build_decision_annex("测试问题", atomic, judge)
        self.assertEqual(ai.annex_calls, 2)
        self.assertNotIn("arithmetic_warning", annex)
        self.assertEqual(annex["budget"][0]["amount"], "480万元")

    def test_validate_decision_annex(self):
        good = {
            "resource_allocation": {"total": "800万元"},
            "budget": [
                {"item": "B", "amount": "480万元"},
                {"item": "A", "amount": "320万元"},
            ],
        }
        bad = {
            "resource_allocation": {"total": "800万元"},
            "budget": [
                {"item": "B", "amount": "400万元"},
                {"item": "A", "amount": "350万元"},
            ],
        }
        self.assertEqual(OutputOrchestrator._validate_decision_annex(good), "")
        self.assertIn("不一致", OutputOrchestrator._validate_decision_annex(bad))

    def test_validate_decision_annex_timeline(self):
        good = {
            "resource_allocation": {"total": "800万元"},
            "timeline": [
                {"phase": "第1-3月", "budget": "300万元"},
                {"phase": "第4-6月", "budget": "300万元"},
                {"phase": "第7-12月", "budget": "200万元"},
            ],
        }
        bad = {
            "resource_allocation": {"total": "800万元"},
            "timeline": [
                {"phase": "第1-3月", "budget": "300万元"},
                {"phase": "第4-6月", "budget": "300万元"},
                {"phase": "第7-12月", "budget": "300万元"},
            ],
        }
        self.assertEqual(OutputOrchestrator._validate_decision_annex(good), "")
        warning = OutputOrchestrator._validate_decision_annex(bad)
        self.assertIn("分阶段预算合计", warning)
        self.assertIn("不一致", warning)

    def test_judge(self):
        orchestrator = OutputOrchestrator(_FakeAI(), _FakeEngine())
        result = orchestrator._run_judge("测试问题", {"role_contributions": {}})
        self.assertEqual(result.get("final_verdict"), "采纳测试")
        roles = {item.get("role") for item in result.get("role_scorecard", [])}
        self.assertEqual(len(roles), 9)
        self.assertIn("大法官", roles)
        self.assertIn("首席发言人", roles)


if __name__ == "__main__":
    unittest.main()
