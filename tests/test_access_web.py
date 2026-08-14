import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import auth as auth_module
from access import web
from access import web_services as app_services
from auth import User


class TestAccessWeb(unittest.TestCase):
    def test_web_app_imports(self):
        tmp = tempfile.mkdtemp(prefix="v5_web_test_")
        old = os.environ.get("CRYSTAL_TREE_DATA_ROOT")
        os.environ["CRYSTAL_TREE_DATA_ROOT"] = tmp
        try:
            from access.web import app, engine

            self.assertGreater(len(app.routes), 0)
            self.assertTrue(hasattr(engine, "parse_crystals"))
        finally:
            if old is None:
                os.environ.pop("CRYSTAL_TREE_DATA_ROOT", None)
            else:
                os.environ["CRYSTAL_TREE_DATA_ROOT"] = old

    def test_backend_login_uses_gui_module(self):
        with mock.patch.object(app_services.subprocess, "Popen") as popen, mock.patch("time.sleep"):
            proc = mock.Mock()
            proc.poll.return_value = None
            popen.return_value = proc
            web.legacy_process_manager = app_services.LegacyProcessManager()
            result = web.backend_login(
                web.BackendLoginRequest(username="admin", password="111111")
            )
            self.assertTrue(result["ok"])
            cmd = popen.call_args.args[0]
            self.assertEqual(cmd, [sys.executable, "-m", "access.gui"])

    def test_user_api_key_roundtrip(self):
        tmp = tempfile.mkdtemp(prefix="v5_auth_test_")
        with mock.patch.object(auth_module, "USER_DB_FILE", str(os.path.join(tmp, "users.json"))):
            auth_module.register_user("user_key_test", "pw")
            self.assertTrue(auth_module.set_user_api_key("user_key_test", "sk-test-key-1234567890"))
            self.assertEqual(auth_module.get_user_api_key("user_key_test"), "sk-test-key-1234567890")
            user = auth_module.get_user("user_key_test")
            self.assertTrue(user.api_key_encrypted)
            self.assertNotEqual(user.api_key_encrypted, "sk-test-key-1234567890")
            self.assertEqual(auth_module.get_user_api_key_masked("user_key_test"), "sk-tes****7890")

    def test_clear_user_api_key(self):
        tmp = tempfile.mkdtemp(prefix="v5_auth_clear_")
        with mock.patch.object(auth_module, "USER_DB_FILE", str(os.path.join(tmp, "users.json"))):
            auth_module.register_user("clear_key_user", "pw")
            auth_module.set_user_api_key("clear_key_user", "sk-clear-key-1234567890")
            self.assertTrue(auth_module.clear_user_api_key("clear_key_user"))
            self.assertEqual(auth_module.get_user_api_key("clear_key_user"), "")
            self.assertEqual(auth_module.get_user_api_key_masked("clear_key_user"), "")

    def test_mask_secret(self):
        self.assertEqual(auth_module.mask_secret("sk-abc1234567890"), "sk-abc****7890")
        self.assertEqual(auth_module.mask_secret(""), "")

    def test_migrate_old_plaintext_key(self):
        tmp = tempfile.mkdtemp(prefix="v5_auth_migrate_")
        users_file = os.path.join(tmp, "users.json")
        with mock.patch.object(auth_module, "USER_DB_FILE", users_file):
            auth_module.register_user("old_key_user", "pw")
            data = json.loads(Path(users_file).read_text(encoding="utf-8"))
            data["old_key_user"]["api_key"] = "sk-old-plain-1234567890"
            data["old_key_user"]["api_key_encrypted"] = ""
            Path(users_file).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            loaded = auth_module._load_users()
            self.assertEqual(auth_module.get_user_api_key("old_key_user"), "sk-old-plain-1234567890")
            self.assertTrue(loaded["old_key_user"].api_key_encrypted)

    def test_delete_user(self):
        tmp = tempfile.mkdtemp(prefix="v5_auth_delete_")
        with mock.patch.object(auth_module, "USER_DB_FILE", str(os.path.join(tmp, "users.json"))):
            auth_module.register_user("delete_user", "pw")
            self.assertTrue(auth_module.delete_user("delete_user"))
            self.assertIsNone(auth_module.get_user("delete_user"))
            self.assertFalse(auth_module.delete_user("delete_user"))

    def test_privacy_endpoint(self):
        import asyncio

        resp = asyncio.run(web.privacy())
        self.assertIn("不收集学生个人信息", resp["content"])

    def test_check_ai_access_uses_user_key(self):
        user = User(username="pro_user", password_hash="x", tier="pro")
        with mock.patch.object(web.auth, "get_user_api_key", return_value="sk-user-key-1234567890"):
            allowed, msg, key = web.check_ai_access_service(web.auth, user, "")
            self.assertTrue(allowed)
            self.assertEqual(key, "sk-user-key-1234567890")

    def test_check_ai_access_rejects_without_key(self):
        user = User(username="pro_no_key", password_hash="x", tier="pro")
        with mock.patch.object(web.auth, "get_user_api_key", return_value=""):
            allowed, msg, key = web.check_ai_access_service(web.auth, user, "")
            self.assertFalse(allowed)
            self.assertEqual(key, "")

    def test_effective_key_requires_user_key(self):
        user = User(username="no_key_user", password_hash="x", tier="pro")
        with mock.patch.object(web.auth, "get_user_api_key", return_value=""):
            with self.assertRaises(Exception):
                web._user_effective_key(user)


if __name__ == "__main__":
    unittest.main()
