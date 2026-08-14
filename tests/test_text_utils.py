import unittest

from core.text_utils import count_output_words


class TestOutputCount(unittest.TestCase):
    def test_count_output_words_mixes_cjk_and_latin(self):
        self.assertEqual(count_output_words("AGI路线选择"), 5)
        self.assertEqual(count_output_words("DeepSeek V4 成本优化"), 6)

    def test_count_output_words_ignores_punctuation_and_whitespace(self):
        self.assertEqual(count_output_words("你好，世界！"), 4)
        self.assertEqual(count_output_words("  方案：A vs B！  "), 5)

    def test_count_output_words_handles_none_and_empty(self):
        self.assertEqual(count_output_words(None), 0)
        self.assertEqual(count_output_words(""), 0)

if __name__ == "__main__":
    unittest.main()
