import os
import unittest

from external.ai_client import AIClient, aggregate_call_log, generate_session_title_from_content
from external.fetcher import ExternalFetcher
from external.network import NetworkManager
from external.search import SearchService
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
        self.assertEqual(totals["prompt_cache_hit_tokens"], 180)
        self.assertEqual(totals["prompt_cache_miss_tokens"], 120)

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


if __name__ == "__main__":
    unittest.main()
