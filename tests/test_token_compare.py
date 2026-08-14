import unittest

from tools.run_debate_token_compare import aggregate_tokens


class TestAggregateTokens(unittest.TestCase):
    def test_sums_cache_hit_and_miss_tokens(self):
        logs = [
            {
                "caller": "chat",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_cache_hit_tokens": 60,
                "prompt_cache_miss_tokens": 40,
            },
            {
                "caller": "chat",
                "prompt_tokens": 200,
                "completion_tokens": 80,
                "prompt_cache_hit_tokens": 120,
                "prompt_cache_miss_tokens": 80,
            },
        ]
        summary = aggregate_tokens(logs)
        self.assertEqual(summary["totals"]["prompt_cache_hit_tokens"], 180)
        self.assertEqual(summary["totals"]["prompt_cache_miss_tokens"], 120)
        self.assertAlmostEqual(summary["totals"]["cache_hit_rate"], 60.0)
        self.assertEqual(summary["by_caller"]["chat"]["prompt_cache_hit_tokens"], 180)

    def test_missing_cache_fields_default_to_zero(self):
        logs = [
            {
                "caller": "chat",
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }
        ]
        summary = aggregate_tokens(logs)
        self.assertEqual(summary["totals"]["prompt_cache_hit_tokens"], 0)
        self.assertEqual(summary["totals"]["prompt_cache_miss_tokens"], 100)
        self.assertAlmostEqual(summary["totals"]["cache_hit_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
