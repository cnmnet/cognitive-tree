import tempfile
import unittest
from pathlib import Path

from data.storage import DBManager, FileIO, HealthChecker
from governance.config import Config


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._original_root = Config.DATA_ROOT
        Config.DATA_ROOT = Path(self.tmp.name)

    def tearDown(self):
        Config.DATA_ROOT = self._original_root
        self.tmp.cleanup()

    def test_file_io_roundtrip(self):
        FileIO.ensure_directories()
        FileIO.write("state", "hello")
        self.assertEqual(FileIO.read("state"), "hello")
        FileIO.append("state", " world")
        self.assertEqual(FileIO.read("state"), "hello world")

    def test_db_manager_sessions(self):
        FileIO.ensure_directories()
        db = DBManager()
        db.create_session("s1", "会话一")
        rows = db.list_sessions()
        self.assertTrue(any(r["id"] == "s1" for r in rows))
        name, history, labels = db.get_session("s1")
        self.assertEqual(name, "会话一")
        db.delete_session("s1")
        self.assertFalse(any(r["id"] == "s1" for r in db.list_sessions()))

    def test_health_checker(self):
        results = HealthChecker.run()
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
