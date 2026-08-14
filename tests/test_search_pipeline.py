import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from external.providers.baidu_qianfan import BaiduQianfanProvider
from external.providers.base import BaseSearchProvider, SearchResult
from external.search_pipeline import SearchPipeline
from governance.config import Config


class _MockProvider(BaseSearchProvider):
    name = "mock"

    def __init__(self, results=None, calls=None, available=True):
        super().__init__()
        self.results = results or []
        self.calls = calls
        self.available = available

    def is_available(self):
        return self.available

    def search(self, query, top_k=5):
        if self.calls is not None:
            self.calls.append(query)
        return self.results[: top_k]


class TestSearchPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)

    def tearDown(self):
        Config.DATA_ROOT = self._old_root
        self.tmp.cleanup()

    def test_baidu_response_parsing(self):
        data = {
            "references": [
                {
                    "id": 1,
                    "title": "万鸟归来 七里海潟湖十年重生",
                    "url": "https://i.ifeng.com/c/8oU2F1wG30G",
                    "date": "2025-10-12 00:00:00",
                    "content": "七里海潟湖位于秦皇岛市北戴河新区",
                    "website": "凤凰网",
                },
                {"id": 2, "title": "", "url": "https://example.com", "content": "缺标题"},
                {"id": 3, "title": "有标题无URL", "url": "", "content": "缺URL"},
            ]
        }
        results = BaiduQianfanProvider.parse_response(data, query="测试", top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "百度千帆")
        self.assertEqual(results[0].published_at, "2025-10-12 00:00:00")
        self.assertTrue(results[0].fingerprint)

    def test_merge_dedup(self):
        shared = SearchResult("百度千帆", "冷链市场", "https://example.com/1", "市场规模")
        pipeline = SearchPipeline()
        merged = pipeline._merge([shared, shared], top_k=5)
        self.assertEqual(len(merged), 1)

    def test_cache_avoids_second_call(self):
        calls = []
        provider = _MockProvider(
            results=[SearchResult("mock", "冷链市场", "https://example.com/1", "内容")],
            calls=calls,
        )
        pipeline = SearchPipeline(cache_ttl_hours=12)
        first = pipeline.search("冷链", top_k=3, providers=[provider])
        second = pipeline.search("冷链", top_k=3, providers=[provider])
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(len(calls), 1)

    def test_unavailable_provider_skipped(self):
        provider = _MockProvider(available=False)
        pipeline = SearchPipeline()
        results = pipeline.search("冷链", top_k=3, providers=[provider])
        self.assertEqual(results, [])

    def test_baidu_provider_requires_key(self):
        with mock.patch.object(Config, "BAIDU_API_KEY", ""), mock.patch.object(Config, "BAIDU_APPBUILDER_API_KEY", ""):
            provider = BaiduQianfanProvider(api_key="", appbuilder_key="")
            self.assertFalse(provider.is_available())

    def test_baidu_post_retries_on_timeout(self):
        from requests.exceptions import Timeout

        class _Resp:
            status_code = 200

            def json(self):
                return {"references": []}

        provider = BaiduQianfanProvider(api_key="k", appbuilder_key="")
        with mock.patch(
            "requests.post",
            side_effect=[Timeout("read timeout"), _Resp()],
        ) as post_mock, mock.patch("time.sleep"):
            data = provider._post("https://example.com", {"messages": []})
        self.assertEqual(data, {"references": []})
        self.assertEqual(post_mock.call_count, 2)

    def test_provider_timeout_skips_slow_source(self):
        class _SlowProvider(_MockProvider):
            name = "slow"

            def search(self, query, top_k=5):
                time.sleep(0.2)
                return [SearchResult("slow", "慢源", "https://slow.example.com", "内容")]

        fast = _MockProvider(
            results=[SearchResult("fast", "快源", "https://fast.example.com", "内容")],
        )
        pipeline = SearchPipeline()
        results = pipeline.search(
            "冷链",
            top_k=3,
            providers=[_SlowProvider(), fast],
            timeout_per_source=0.02,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "fast")

    def test_total_timeout_skips_remaining_sources(self):
        calls = []

        class _Fast(_MockProvider):
            name = "fast"

            def search(self, query, top_k=5):
                calls.append("fast")
                return [SearchResult("fast", "快源", "https://fast.example.com", "内容")]

        class _Second(_MockProvider):
            name = "second"

            def search(self, query, top_k=5):
                calls.append("second")
                return []

        with mock.patch(
            "external.search_pipeline.time.monotonic",
            side_effect=[0.0, 0.0, 100.0],
        ):
            pipeline = SearchPipeline()
            results = pipeline.search(
                "冷链",
                providers=[_Fast(), _Second()],
                total_timeout=10,
            )
        self.assertEqual(calls, ["fast"])
        self.assertEqual(len(results), 1)

    def test_stage_normalize_cleans_and_filters(self):
        pipeline = SearchPipeline()
        kept = pipeline._stage_normalize(
            [
                SearchResult("百度千帆", "冷链市场", "https://example.com/1", "内容"),
                SearchResult("百度千帆", "（占位）", "https://example.com/2", "内容"),
                SearchResult("百度千帆", "模拟结果", "https://example.com/3", "内容"),
                SearchResult("arXiv", "有标题无URL", "", "内容"),
            ],
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].url, "https://example.com/1")


if __name__ == "__main__":
    unittest.main()
