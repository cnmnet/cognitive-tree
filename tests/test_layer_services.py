import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from auth.services import check_ai_access, update_user_api_key
from data.services import get_session_record, history_context, update_last_round_label, visible_sessions
from evolution.services import run_force_exploration, run_godel_evolution
from external.services import duckduckgo_search, extract_keywords, run_sync_vector_store
from governance.services import current_profile, load_debate_roles, load_roles
from harness.services import get_skill, list_skills
from webhook.services import create_checkout_session


class FakeFiles:
    def __init__(self):
        self.data = {}

    def read(self, name):
        return self.data.get(name, "")

    def exists(self, name):
        return name in self.data

    def write(self, name, content):
        self.data[name] = content

    def append(self, name, content):
        self.data[name] = self.data.get(name, "") + content


class FakeDB:
    def __init__(self):
        self.sessions = {}

    def create_session(self, sid, name):
        self.sessions[sid] = (name, [], [])

    def get_session(self, sid):
        return self.sessions.get(sid, (None, [], []))

    def update_session(self, sid, history, name):
        _old_name, _old_history, old_labels = self.sessions.get(sid, (None, [], []))
        labels = old_labels
        if history and isinstance(history[0], dict):
            labels = [item.get("label") for item in history]
            history = [(item.get("role"), item.get("content")) for item in history]
        self.sessions[sid] = (name, history, labels)

    def rename_session(self, sid, name):
        if sid in self.sessions:
            self.sessions[sid] = (name, self.sessions[sid][1], [])

    def list_sessions(self):
        return [(sid, name, "now") for sid, (name, _, _) in self.sessions.items()]


class FakeAuth:
    def get_user_api_key(self, username):
        return ""

    def get_user_api_key_masked(self, username):
        return ""

    def get_trial_remaining(self, username):
        return 5

    def set_user_api_key(self, username, key):
        self.key = key

    def mask_secret(self, key):
        return key[:6] + "****"

    def verify_password(self, password, hashed):
        return password == hashed

    def delete_user(self, username):
        pass


class FakeAI:
    def __init__(self, api_key=""):
        self.api_key = api_key

    def chat(self, prompt, system=None, **kwargs):
        return "回复OK"


class FakeMeta:
    def trigger_gödel_evolution(self, role):
        return {"applied": True, "role": role}

    def __init__(self):
        self.force_explorer = SimpleNamespace(
            run_scheduled_exploration=lambda: {"success": True, "processed": 1}
        )


class FakeEngine:
    def __init__(self):
        self.meta = FakeMeta()

    def get_all_skills(self):
        return ["C001"]

    def get_skill_path(self, crystal_id):
        return self.skill_dir

    def get_skill_crystal(self, crystal_id):
        return SimpleNamespace(
            content="测试晶体",
            layer=SimpleNamespace(value="L1"),
        )

    def validate_skill(self, crystal_id):
        return {"valid": True}

    def sync_vector_store(self):
        return {"status": "synced", "synced": 1, "total": 1}


class TestLayerServices(unittest.TestCase):
    def test_data_history_context(self):
        db = FakeDB()
        db.create_session("S1", "会话")
        db.update_session("S1", [("user", "问题"), ("assistant", "回答")], "会话")
        ctx = history_context(db, "S1", "问题")
        self.assertIn("问题", ctx)
        record = get_session_record(db, "S1")
        self.assertEqual(len(record["messages"]), 2)
        self.assertEqual(len(record["questions"]), 1)

    def test_data_visible_sessions(self):
        db = FakeDB()
        db.create_session("S1", "新会话 12:00")
        db.create_session("S2", "战略方案")
        db.update_session("S2", [("user", "问题")], "战略方案")
        sessions = db.list_sessions()
        self.assertEqual([sid for sid, _ in visible_sessions(db, sessions, "")], ["S2"])
        self.assertEqual([sid for sid, _ in visible_sessions(db, sessions, "战略")], ["S2"])
        self.assertEqual(visible_sessions(db, sessions, "不存在"), [])

    def test_data_update_last_round_label(self):
        db = FakeDB()
        db.create_session("S1", "会话")
        db.update_session(
            "S1",
            [("user", "问题A"), ("assistant", "回答A"), ("user", "问题B")],
            "会话",
        )
        update_last_round_label(db, "S1", "问题B标题")
        _name, _history, labels = db.get_session("S1")
        self.assertEqual(labels[2], "问题B标题")

    def test_external_extract_keywords(self):
        self.assertTrue(extract_keywords("如何制定一个战略方案"))

    def test_external_sync_vector_store(self):
        logs = []
        run_sync_vector_store(
            FakeEngine(),
            lambda m, level="system": logs.append((m, level)),
            lambda: None,
        )
        self.assertTrue(logs)

    def test_external_duckduckgo_search(self):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            text='<a class="result__a">标题</a><a class="result__snippet">摘要</a>',
        )
        with mock.patch("external.services.requests.post", return_value=response):
            result = duckduckgo_search(
                ["晶体"],
                True,
                lambda: "test-agent",
            )
        self.assertIn("标题", result)

    def test_governance_load_roles(self):
        files = FakeFiles()
        files.data["roles"] = '{"radical": {"name": "激进者", "instruction": "测试"}}'
        roles = load_roles(files)
        self.assertTrue(any(r["key"] == "radical" for r in roles))

    def test_governance_current_profile(self):
        profile = current_profile("balanced")
        self.assertIsInstance(profile, dict)
        self.assertEqual(current_profile("unknown_mode"), profile)

    def test_governance_load_debate_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            roles_path = Path(tmp) / "roles.json"
            config = SimpleNamespace(get_path=lambda key: roles_path)
            file_io = SimpleNamespace(write=lambda name, content: None)
            roles = load_debate_roles(config, file_io)
            self.assertGreaterEqual(len(roles), 5)
            self.assertTrue(any(r["key"] == "radical" for r in roles))

    def test_harness_skills(self):
        engine = FakeEngine()
        with tempfile.TemporaryDirectory() as tmp:
            engine.skill_dir = __import__("pathlib").Path(tmp)
            (engine.skill_dir / "CRYSTAL.md").write_text("x", encoding="utf-8")
            self.assertEqual(list_skills(engine)["total"], 1)
            detail = get_skill(engine, "C001")
            self.assertEqual(detail["id"], "C001")
            self.assertIn("CRYSTAL.md", detail["files"])

    def test_evolution_services(self):
        done = []
        run_godel_evolution(
            FakeEngine(),
            "radical",
            lambda result: done.append(result["applied"]),
            lambda e: done.append(str(e)),
            lambda: None,
        )
        self.assertEqual(done, [True])

        explored = []
        run_force_exploration(
            FakeEngine(),
            lambda result: explored.append(result["processed"]),
            lambda e: explored.append(str(e)),
            lambda: None,
        )
        self.assertEqual(explored, [1])

    def test_auth_services(self):
        auth = FakeAuth()
        result = update_user_api_key(
            auth,
            FakeAI,
            "user",
            "sk-valid-key-1234567890",
        )
        self.assertTrue(result["ok"])
        allowed, _, key = check_ai_access(auth, SimpleNamespace(username="user"), "")
        self.assertFalse(allowed)
        self.assertEqual(key, "")

    def test_webhook_create_checkout_session(self):
        config = SimpleNamespace(
            STRIPE_SECRET_KEY="sk_test",
            STRIPE_PRICE_ID="price_1",
        )
        stripe = SimpleNamespace(
            checkout=SimpleNamespace(
                Session=SimpleNamespace(
                    create=staticmethod(
                        lambda **kw: SimpleNamespace(id="cs_test", url="https://pay")
                    )
                )
            )
        )
        result = create_checkout_session(config, stripe, "user")
        self.assertEqual(result["session_id"], "cs_test")


if __name__ == "__main__":
    unittest.main()
