import unittest
from unittest import mock

from external.fetcher import ExternalFetcher
from external.summary import summarize_items, summarize_text
from governance.config import Config
from harness.processors.debate import DebateEngine
from harness.processors.planner import DailyPlanner


class TestQianfanSlice(unittest.TestCase):
    def tearDown(self):
        Config.ENABLE_BAIDU_QIANFAN = False
        Config.QIANFAN_OVERVIEW_MODE = "synthesized"

    def test_disabled_returns_empty(self):
        Config.ENABLE_BAIDU_QIANFAN = False
        self.assertEqual(ExternalFetcher().fetch_qianfan("测试查询"), [])

    def test_enabled_without_key_returns_empty(self):
        Config.ENABLE_BAIDU_QIANFAN = True
        with mock.patch.object(Config, "BAIDU_API_KEY", ""), mock.patch.object(
            Config, "BAIDU_APPBUILDER_API_KEY", ""
        ):
            self.assertEqual(ExternalFetcher().fetch_qianfan("测试查询"), [])

    def test_daily_plan_logs_degrade_when_qianfan_empty(self):
        Config.ENABLE_BAIDU_QIANFAN = True
        logs = []
        fetcher = mock.Mock()
        fetcher.fetch_all.return_value = {}
        fetcher.build_insights.return_value = []
        fetcher.build_structured_insights.return_value = []
        fetcher.fetch_arxiv_papers.return_value = []
        fetcher.fetch_baidu_news.return_value = []
        fetcher.fetch_qianfan.return_value = []
        planner = DailyPlanner(
            engine=mock.Mock(),
            ai_client=mock.Mock(),
            fetcher=fetcher,
            log_callback=lambda message, level="system": logs.append((message, level)),
            update_status_callback=lambda message: None,
        )
        planner.keywords = ["测试关键词"]
        planner._collect_external_info()
        self.assertTrue(
            any("降级到现有抓取" in message and level == "warning" for message, level in logs)
        )

    def test_debate_external_overview_logs_degrade_when_qianfan_empty(self):
        Config.ENABLE_BAIDU_QIANFAN = True
        logs = []
        debate = DebateEngine.__new__(DebateEngine)
        debate.ai = mock.Mock()
        debate.ai.chat.return_value = "外部知识总览：案例A、案例B。"
        debate.ai.chat_json.return_value = {"queries": ["补充查询"]}
        debate.log = lambda message, level="system": logs.append((message, level))
        with mock.patch.object(
            ExternalFetcher, "fetch_qianfan", return_value=[]
        ):
            result = debate._fetch_external_overview("测试问题")
        self.assertIn("外部知识总览", result)
        self.assertTrue(
            any("降级为模型知识生成" in message and level == "warning" for message, level in logs)
        )

    def test_debate_external_overview_extractive_skips_ai(self):
        Config.ENABLE_BAIDU_QIANFAN = True
        Config.QIANFAN_OVERVIEW_MODE = "extractive"
        debate = DebateEngine.__new__(DebateEngine)
        debate.ai = mock.Mock()
        debate.ai.chat_json.return_value = {"queries": ["补充查询"]}
        debate.log = lambda message, level="system": None
        items = [
            {"title": "真实文章A", "summary": "这是真实文章摘要A。" * 10, "link": "https://a.example"},
            {"title": "真实文章B", "summary": "这是真实文章摘要B。" * 10, "link": "https://b.example"},
        ]
        with mock.patch.object(ExternalFetcher, "fetch_qianfan", return_value=items):
            result = debate._fetch_external_overview("测试问题")
        self.assertIn("千帆检索摘要", result)
        self.assertIn("真实文章A", result)
        debate.ai.chat.assert_not_called()
        debate.ai.chat_json.assert_called_once()

    def test_debate_external_overview_synthesized_injects_material(self):
        Config.ENABLE_BAIDU_QIANFAN = True
        Config.QIANFAN_OVERVIEW_MODE = "synthesized"
        debate = DebateEngine.__new__(DebateEngine)
        debate.ai = mock.Mock()
        debate.ai.chat.return_value = "综合后的外部总览。"
        debate.ai.chat_json.return_value = {"queries": ["补充查询"]}
        debate.log = lambda message, level="system": None
        items = [{"title": "真实文章C", "summary": "这是真实文章摘要C。" * 10, "link": "https://c.example"}]
        with mock.patch.object(ExternalFetcher, "fetch_qianfan", return_value=items):
            result = debate._fetch_external_overview("测试问题")
        self.assertEqual(result, "综合后的外部总览。")
        prompt = debate.ai.chat.call_args[0][0]
        self.assertIn("真实搜索结果", prompt)
        self.assertIn("真实文章C", prompt)

    def test_generate_qianfan_queries_uses_deepseek(self):
        debate = DebateEngine.__new__(DebateEngine)
        debate.ai = mock.Mock()
        debate.ai.chat_json.return_value = {"queries": ["学术案例", "政策动态"]}
        debate.log = lambda message, level="system": None
        question = "如何平衡长期目标与短期资源约束？"
        queries = debate._generate_qianfan_queries(question)
        self.assertEqual(queries[0], question)
        self.assertIn("学术案例", queries)
        self.assertIn("政策动态", queries)

    def test_generate_qianfan_queries_falls_back_locally(self):
        debate = DebateEngine.__new__(DebateEngine)
        debate.ai = mock.Mock()
        debate.ai.chat_json.side_effect = Exception("boom")
        debate.log = lambda message, level="system": None
        question = "如何设计一个多变量优化框架并评估综合策略，同时平衡长期目标与短期资源约束？"
        queries = debate._generate_qianfan_queries(question)
        self.assertGreaterEqual(len(queries), 2)
        self.assertEqual(queries[0], question)

    def test_summarize_text_keeps_date_and_number_sentences(self):
        content = ("无关紧要的填充内容。" * 20) + "2026年3月1日，成本下降40%，市场规模达200亿元。"
        result = summarize_text(content, 120)
        self.assertIn("2026年3月1日", result)
        self.assertIn("40%", result)

    def test_summarize_items_prefers_rich_items(self):
        items = [
            {"title": "空泛标题A", "summary": "普通内容。" * 20, "link": "https://a.example"},
            {"title": "数据标题", "summary": "2026年投资回报率提升30%，市场规模500亿元。" * 10, "link": "https://b.example"},
            {"title": "空泛标题B", "summary": "普通内容。" * 20, "link": "https://c.example"},
        ]
        result = summarize_items(items, max_items=2, per_item_chars=150)
        titles = [item["title"] for item in result]
        self.assertIn("数据标题", titles)
        rich_summary = next(item["summary"] for item in result if item["title"] == "数据标题")
        self.assertIn("2026年", rich_summary)
        self.assertIn("30%", rich_summary)


if __name__ == "__main__":
    unittest.main()
