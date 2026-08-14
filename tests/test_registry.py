import unittest

from core.registry import ProcessorRegistry
from harness.processors import register_default_processors


class TestRegistry(unittest.TestCase):
    def test_register_and_get(self):
        registry = ProcessorRegistry()
        register_default_processors(registry)
        self.assertIn("debate", registry.names())
        self.assertEqual(registry.get("debate").name, "debate")

    def test_duplicate_rejected(self):
        registry = ProcessorRegistry()
        register_default_processors(registry)
        with self.assertRaises(ValueError):
            register_default_processors(registry)

    def test_missing_processor(self):
        registry = ProcessorRegistry()
        with self.assertRaises(KeyError):
            registry.get("missing")


if __name__ == "__main__":
    unittest.main()
