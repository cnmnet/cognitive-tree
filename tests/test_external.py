import os
import unittest

from external.ai_client import AIClient, aggregate_call_log, generate_session_title_from_content
from external.fetcher import ExternalFetcher
from external.network import NetworkManager
from external.search import SearchService
from external.services import score_cognitive_level
from governance.config import Config
from data.storage import FileIO


class TestExternal(unittest.TestCase):
    def setUp(self):
        self._old_key = os.environ.get("DEEPSEEK_API_KEY")
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def tearDown(self):
        if self._old_key is not None:
            os.environ["DEEPSEEK_API_KEY"] = self._old_key
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_ai_client_missing_key(self):
        ai = AIClient(api_key="")
        self.assertIn("未配置", ai.chat("hello"))

    def test_ai_client_json_fallback(self):
        ai = AIClient(api_key="")
        self.assertIn("error", ai.chat_json("hello"))

    def test_aggregate_call_log_totals(self):
        logs = [
            {
                "caller": "chat",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_cache_hit_tokens": 60,
                "prompt_cache_miss_tokens": 40,
            },
            {
                "caller": "chat_json",
                "prompt_tokens": 200,
                "completion_tokens": 80,
                "prompt_cache_hit_tokens": 120,
                "prompt_cache_miss_tokens": 80,
            },
        ]
        totals = aggregate_call_log(logs)
        self.assertEqual(totals["calls"], 2)
        self.assertEqual(totals["prompt_tokens"], 300)
        self.assertEqual(totals["completion_tokens"], 130)
        self.assertEqual(totals["total_tokens"], 430)
        self.assertEqual(totals["prompt_cache_hit_tokens"], 180)
        self.assertEqual(totals["prompt_cache_miss_tokens"], 120)
        self.assertEqual(totals["by_caller"]["chat"]["calls"], 1)
        self.assertEqual(totals["by_caller"]["chat"]["prompt_tokens"], 100)
        self.assertEqual(totals["by_caller"]["chat_json"]["completion_tokens"], 80)

    def test_title_fallback(self):
        title = generate_session_title_from_content("你好，这是一段很长很长的对话内容用于测试")
        self.assertTrue(title)

    def test_search_tokens_and_score(self):
        self.assertTrue(SearchService._tokens("机器学习AI"))
        self.assertGreater(SearchService._score("机器学习", "机器学习是当前研究热点"), 0)

    def test_fetcher_insights(self):
        fetcher = ExternalFetcher(file_io=FileIO)
        sample = {
            "ai_papers": ["论文A (发布于: 2026-01-01)"],
            "hf_papers": [],
            "llm_news": {},
            "neuro_papers": [],
        }
        self.assertTrue(fetcher.build_insights(sample))
        structured = fetcher.build_structured_insights(sample)
        self.assertEqual(structured[0]["type"], "arxiv")

    def test_network_user_agent(self):
        self.assertIn(NetworkManager.get_random_user_agent(), Config.USER_AGENTS)

    def test_cognitive_scorer_pending_without_valid_ai(self):
        class FakeAI:
            def __init__(self):
                self.calls = 0

            def chat_json(self, prompt, temperature=0.3):
                self.calls += 1
                return {"error": "mock failure"}

        result = score_cognitive_level("报告文本", ai_client=FakeAI())
        self.assertEqual(result["status"], "pending_llm")
        self.assertIsNone(result["cognitive_level"])

    def test_cognitive_scorer_parses_llm_result(self):
        class FakeAI:
            def chat_json(self, prompt, temperature=0.3):
                return {
                    "dimensions": {
                        "knowledge_lifecycle": 90,
                        "human_ai_collaboration_reconstruction": 90,
                        "cognitive_domestication_awareness": 85,
                        "tree_decomposition_potential": 95,
                        "long_term_asset_irreplaceability": 95,
                        "hidden_trap_detection": 80,
                    },
                    "surprise_winning": {
                        "score": 92,
                        "sub_scores": {
                            "counterintuitive": 95,
                            "opportunity_window": 90,
                            "asymmetric_payoff": 90,
                        },
                        "evidence": "反常识、机会窗口、非对称收益",
                    },
                }

        result = score_cognitive_level("报告文本", ai_client=FakeAI())
        self.assertEqual(result["status"], "scored")
        self.assertEqual(len(result["dimensions"]), 6)
        self.assertEqual(result["surprise_winning"]["score"], 92.0)
        self.assertIn("反常识", result["strategy_tags"])
        self.assertEqual(result["cognitive_level"], "structured")

    def test_cognitive_scorer_retries_invalid_json(self):
        class FakeAI:
            def __init__(self):
                self.calls = 0

            def chat_json(self, prompt, temperature=0.3):
                self.calls += 1
                return {"error": "bad"}

        result = score_cognitive_level("报告文本", ai_client=FakeAI())
        self.assertEqual(result["status"], "pending_llm")


if __name__ == "__main__":
    unittest.main()
