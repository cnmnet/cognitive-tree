import tempfile
import unittest
from pathlib import Path

from core.persistence import JSONPatch, PatchStore


class TestPatchStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PatchStore(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_and_rollback(self):
        patch = JSONPatch(self.store, "roles", {"radical": "激进者"})
        self.assertTrue(patch.apply())
        self.assertEqual(self.store._read_data()["roles"], {"radical": "激进者"})
        self.assertTrue(patch.rollback())
        self.assertNotIn("roles", self.store._read_data())
        self.assertEqual(patch.status, "rolled_back")

    def test_precondition_hash_guards_apply(self):
        patch = JSONPatch(self.store, "roles", {"radical": "激进者"})
        self.store._write_data({"roles": {"someone": "other"}})
        with self.assertRaises(ValueError):
            patch.apply()

    def test_patch_journal(self):
        patch = JSONPatch(self.store, "roles", {"radical": "激进者"})
        patch.apply()
        rows = self.store.list_patches()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "applied")
        patch.rollback()
        rows = self.store.list_patches()
        self.assertEqual(rows[0]["status"], "rolled_back")


if __name__ == "__main__":
    unittest.main()
