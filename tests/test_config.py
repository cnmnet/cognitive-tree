import unittest

from governance.config import Config


class TestConfig(unittest.TestCase):
    def test_get_path_under_data_root(self):
        path = Config.get_path("crystals")
        self.assertTrue(str(path).startswith(str(Config.DATA_ROOT)))

    def test_defaults(self):
        self.assertGreater(Config.MAX_RETRIES, 0)
        self.assertIn("radical", Config.ROLE_QUALITY_CONFIG)
        self.assertTrue(Config.GODEL_USE_MOCK_EXTERNAL is False)


if __name__ == "__main__":
    unittest.main()
