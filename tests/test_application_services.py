import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    from access.gui_parts.services import build_rumad_status_text
except ImportError:
    build_rumad_status_text = None
from harness.session_jobs import JobManager
from governance.services import load_roles
from harness.services import (
    build_crystallization_prompt,
    build_pending_card_view_data,
    build_performance_table,
    build_session_context,
    clamp_debate_rounds,
    confirm_pending_card,
    confirm_pending_card_with_content,
    delete_asset,
    force_archive_holes,
    format_crystal_update_preview,
    generate_dual_titles,
    generate_elegant_narrative,
    generate_round_label_simple,
    is_complex_question,
    normalize_crystal_response,
    parse_pending_card_block,
    parse_keyword_input,
    patch_asset,
    question_display_lines,
    resolve_round_titles,
    run_batch_process_task,
    run_chat_task,
    run_crystallize_task,
    run_daily_plan_task,
    run_deep_reasoning_task,
    run_file_chat_task,
    run_gui_batch_task,
    run_gui_chat_task,
    run_gui_crystal_task,
    run_gui_file_chat_task,
    run_gui_daily_plan,
    run_single_deep_reasoning,
    save_task_cards,
    save_report_to_desktop,
    simple_keywords,
    similar_crystal_pairs,
    task_cards,
    update_gui_files,
    vote_role,
    wisdom_commons_display,
)
from core.text_utils import normalize_text


class FakeConfig:
    L1_MAX = 5


class FakeEngine:
    def __init__(self):
        self.layer_state = {
            "layers": {},
            "heat_map": {},
            "last_accessed": {},
            "manual_override": {},
        }
        self.crystals = []
        self.fingerprint_extractor = SimpleNamespace(
            get_fingerprint=lambda: SimpleNamespace(confidence=0.8, total_interactions=1),
            get_cognitive_operators=lambda fp: "ops",
            extract=lambda *args, **kwargs: None,
        )

    def get_attention_context(self):
        return [], []

    def get_associative_crystals(self, user_input, top_k=8):
        return []

    def parse_crystals(self):
        return self.crystals

    def load_layer_state(self):
        return self.layer_state

    def update_crystal_layers(self):
        return [], [], []

    def save_layer_state(self, state):
        self.layer_state = state

    def _append_change_log(self, *args):
        pass

    def _simple_similarity(self, content, other):
        return 0.0

    def quality_gate_g2(self, reply, extra):
        return {"passed": True, "reason": "ok"}

    def vote_role(self, role_key, support):
        return 0.8

    def create_crystal(self, crystal_id, content, links, source, **kwargs):
        self.crystals.append(SimpleNamespace(id=crystal_id, content=content))

    def _load_wisdom_commons(self):
        return {
            "crystals": [
                {
                    "crystal_id": "C001",
                    "content": "智慧晶体",
                    "score": 30,
                    "usage_count": 2,
                    "status": "active",
                }
            ]
        }


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
        self.sessions[sid] = (name, history, [])

    def rename_session(self, sid, name):
        if sid in self.sessions:
            self.sessions[sid] = (name, self.sessions[sid][1], [])

    def list_sessions(self):
        return [
            (sid, name, "")
            for sid, (name, _history, _labels) in self.sessions.items()
        ]


class FakeAI:
    def __init__(self, api_key=""):
        self.api_key = api_key

    def chat_with_history(self, history, context=None, **kwargs):
        return "AI 回复"

    def chat_json(self, prompt, **kwargs):
        return {"session_title": "会话标题", "round_title": "本轮标题"}

    def chat(self, prompt, system=None, **kwargs):
        return "深度回复"


class FakeBatch:
    def __init__(self, ai, log=None):
        self.ai = ai
        self.log = log

    def extract_text_from_file(self, path):
        return ["这是一份测试文件内容"]


class FakeBatchRunner:
    def __init__(self, ai, log=None):
        self.ai = ai
        self.log = log

    def process_folder(
        self,
        folder,
        mode,
        fast_mode,
        progress,
        stop_flag,
        hist,
    ):
        hist("user", "批量消息")
        progress(50)


class FakeFetcher:
    pass


class FakePlanner:
    def __init__(self, engine, ai, fetcher, log, status):
        self.engine = engine
        self.ai = ai
        self.fetcher = fetcher

    def run(self, **kwargs):
        return {"done": True, "keywords": kwargs.get("intent_keywords")}


class TestApplicationServices(unittest.TestCase):
    def test_normalize_text_compacts_whitespace_and_limits(self):
        self.assertEqual(normalize_text("  a\n   b  ", 3), "a b"[0:3])
        self.assertEqual(normalize_text(None), "")

    def test_build_crystallization_prompt_has_schema_and_constraints(self):
        prompt = build_crystallization_prompt(
            FakeEngine(),
            FakeConfig(),
            {"C001"},
            "健康食品怎么选",
            "搜索摘要",
            include_constraints=True,
        )
        self.assertIn("返回 JSON schema", prompt)
        self.assertIn("约束：", prompt)
        self.assertIn("C001", prompt)

    def test_normalize_crystal_response_assigns_ids(self):
        result = normalize_crystal_response(
            FakeFiles(),
            FakeEngine(),
            set(),
            {
                "new_crystals": [{"id": "", "content": "第一条晶体", "links": []}],
                "new_holes": [{"content": "一个孔洞", "urgency": 0.9, "layer": 2}],
            },
        )
        self.assertEqual(result["new_crystals"][0]["id"], "C001")
        self.assertEqual(result["new_holes"][0]["id"], "H001")

    def test_normalize_crystal_response_rejects_non_dict(self):
        self.assertEqual(
            normalize_crystal_response(FakeFiles(), FakeEngine(), set(), "bad"),
            {"error": "AI返回不是JSON对象"},
        )

    def test_task_cards_roundtrip(self):
        files = FakeFiles()
        cards = [{"id": "T1", "title": "任务"}]
        save_task_cards(files, cards)
        self.assertEqual(task_cards(files), cards)

    def test_load_roles_has_fallback_roles(self):
        roles = load_roles(FakeFiles())
        self.assertEqual(len(roles), 9)
        self.assertTrue(any(role["key"] == "judge" for role in roles))

    def test_patch_asset_updates_layer(self):
        engine = FakeEngine()
        engine.crystals = [SimpleNamespace(id="C001")]
        patch_asset(engine, "C001", "L2", fixed=None)
        self.assertEqual(engine.layer_state["layers"]["C001"], "L2")

    def test_delete_asset_removes_crystal_row(self):
        files = FakeFiles()
        files.data["crystals"] = "| C001 | 内容 | — |\n| C002 | 内容2 | — |\n"
        engine = FakeEngine()
        self.assertTrue(delete_asset(files, engine, "C001"))
        self.assertNotIn("C001", files.data["crystals"])

    def test_confirm_pending_card_creates_crystal(self):
        files = FakeFiles()
        files.data["pending"] = "## PENDING-20260811-001\n- 内容：测试晶体\n"
        engine = FakeEngine()
        result = confirm_pending_card(files, engine, "PENDING-20260811-001", "测试晶体")
        self.assertTrue(result["ok"])
        self.assertEqual(result["crystal_id"], "C001")
        self.assertIn("C001", files.data["crystals"])

    def test_run_chat_task_appends_reply(self):
        db = FakeDB()
        db.create_session("S1", "测试会话")
        result = run_chat_task(
            db,
            FakeEngine(),
            FakeAI,
            "S1",
            "sk-test",
        )
        self.assertIn("AI 回复", result["reply"])
        self.assertIn("回答质量评分", result["reply"])
        self.assertIn("total", result["score"])
        _, history, _ = db.get_session("S1")
        self.assertEqual(history[-1][0], "assistant")
        self.assertIn("回答质量评分", history[-1][1])

    def test_run_crystallize_task_returns_preview(self):
        db = FakeDB()
        db.create_session("S1", "测试会话")
        result = run_crystallize_task(
            db,
            FakeEngine(),
            FakeAI,
            "S1",
            "sk-test",
            "问题",
            True,
            lambda *args: "prompt",
            lambda raw: {"ok": True},
        )
        self.assertEqual(result["preview"], {"ok": True})

    def test_run_file_chat_task_appends_messages(self):
        db = FakeDB()
        db.create_session("S1", "测试会话")
        result = run_file_chat_task(
            db,
            FakeAI,
            FakeBatch,
            "S1",
            "sk-test",
            "fake.txt",
            "测试.txt",
        )
        self.assertIn("AI 回复", result["reply"])
        self.assertIn("回答质量评分", result["reply"])
        _, history, _ = db.get_session("S1")
        self.assertTrue(history[0][0] == "user" and "[文件内容]" in history[0][1])
        self.assertEqual(history[-1][0], "assistant")
        self.assertIn("回答质量评分", history[-1][1])

    def test_run_batch_process_task(self):
        progress_values = []
        history_rows = []
        result = run_batch_process_task(
            FakeAI,
            FakeBatchRunner,
            "sk-test",
            "folder",
            "chat",
            True,
            True,
            "S1",
            lambda value: progress_values.append(value),
            lambda: False,
            lambda session_id, role, content: history_rows.append(
                (session_id, role, content)
            ),
        )
        self.assertEqual(result["folder"], "folder")
        self.assertTrue(progress_values)
        self.assertEqual(history_rows[0][0], "S1")

    def test_run_daily_plan_task(self):
        result = run_daily_plan_task(
            FakeEngine(),
            FakeAI,
            FakeFetcher,
            FakePlanner,
            "sk-test",
            ["健康"],
            900,
            lambda: False,
            lambda data: None,
            lambda *args: None,
            lambda *args: None,
        )
        self.assertTrue(result["done"])
        self.assertEqual(result["keywords"], ["健康"])

    def test_run_deep_reasoning_task_single_path(self):
        db = FakeDB()
        db.create_session("S1", "测试会话")
        result = run_deep_reasoning_task(
            FakeEngine(),
            FakeAI,
            lambda ai, roles, log: None,
            "job1",
            "S1",
            "sk-test",
            "simple",
            "问题",
            2,
            lambda: [],
            lambda session_id, user_input: user_input,
            lambda session_id, role, content: None,
            lambda *args: None,
        )
        self.assertIn("【综合最终答案】", result["reply"])
        self.assertIn("回答质量评分", result["reply"])
        self.assertIn("total", result["score"])

    def test_job_manager_roundtrip(self):
        manager = JobManager()
        job_id = manager.create("chat")
        manager.set(job_id, progress=10)
        manager.log(job_id, "开始")
        manager.run(job_id, lambda: {"ok": True})
        job = manager.jobs[job_id]
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"], {"ok": True})
        self.assertTrue(job["logs"])

    def test_is_complex_question(self):
        self.assertTrue(
            is_complex_question(
                "如何制定一套可行的战略方案并且兼顾成本、风险和时间约束？"
            )
        )
        self.assertFalse(is_complex_question("你好"))

    def test_build_performance_table(self):
        lines = build_performance_table(
            [
                {
                    "role": "激进者",
                    "contribution_percent": 30,
                    "kpi_score": 8,
                    "status": "采纳",
                    "reason": "补充关键假设",
                }
            ]
        )
        self.assertTrue(any("角色" in line for line in lines))
        self.assertTrue(any("激进者" in line for line in lines))
        self.assertTrue(any("30%" in line for line in lines))
        self.assertTrue(any("大法官" in line for line in lines))
        self.assertTrue(any("首席发言人" in line for line in lines))

    def test_format_crystal_update_preview(self):
        similar_fn = lambda content: [
            (0.9, SimpleNamespace(id="C001", content="相似晶体"))
        ]
        text = format_crystal_update_preview(
            {
                "report_summary": "完成",
                "new_crystals": [
                    {
                        "id": "C002",
                        "content": "新晶体",
                        "links": [],
                    }
                ],
            },
            similar_fn,
        )
        self.assertIn("C002", text)
        self.assertIn("可能重复", text)
        self.assertIn("C001", text)

    def test_generate_dual_titles(self):
        titles = generate_dual_titles(
            "问题",
            "回答",
            ["旧标题"],
            lambda: FakeAI(),
        )
        self.assertEqual(titles[0], "会话标题")
        self.assertEqual(titles[1], "本轮标题")

    def test_generate_round_label_simple_dedup(self):
        title = generate_round_label_simple(
            "问题",
            lambda: FakeAI(),
            ["深度回复"],
        )
        self.assertTrue(title.startswith("深度回复"))

    def test_generate_elegant_narrative(self):
        text = generate_elegant_narrative(
            FakeAI(),
            "核心观点",
            "详细建议",
        )
        self.assertIsInstance(text, str)
        self.assertTrue(text)

    def test_clamp_debate_rounds(self):
        self.assertEqual(clamp_debate_rounds(1), 2)
        self.assertEqual(clamp_debate_rounds(20), 12)
        self.assertEqual(clamp_debate_rounds("bad"), 2)

    def test_run_gui_chat_task(self):
        done = []
        run_gui_chat_task(
            FakeEngine(),
            FakeAI(),
            "sk-test",
            [("user", "你好")],
            lambda m, level="system": None,
            lambda reply: done.append(reply),
        )
        self.assertEqual(len(done), 1)
        self.assertIn("AI 回复", done[0])
        self.assertIn("回答质量评分", done[0])

    def test_run_gui_crystal_task(self):
        previews = []
        done = []
        run_gui_crystal_task(
            FakeEngine(),
            FakeAI(),
            "sk-test",
            "问题",
            True,
            lambda text: [],
            lambda keywords: "",
            lambda u, s, holes, crystals: "prompt",
            lambda raw: {"ok": True},
            lambda m, level="system": None,
            lambda preview: previews.append(preview),
            lambda: done.append(True),
        )
        self.assertEqual(previews, [{"ok": True}])
        self.assertEqual(done, [True])

    def test_run_gui_file_chat_task(self):
        done = []
        run_gui_file_chat_task(
            FakeEngine(),
            FakeAI(),
            "sk-test",
            [("user", "文件问题")],
            lambda reply: done.append(reply),
        )
        self.assertEqual(len(done), 1)
        self.assertIn("AI 回复", done[0])
        self.assertIn("回答质量评分", done[0])

    def test_run_gui_batch_task(self):
        class _FakeBatch:
            def process_folder(self, folder, mode, fast_mode, progress, stop, history_cb):
                progress(50)
                history_cb("user", "内容")

        done = []
        run_gui_batch_task(
            _FakeBatch(),
            "sk-test",
            "D:/tmp",
            "crystal",
            True,
            lambda value: None,
            lambda: False,
            lambda role, content: None,
            lambda: done.append(True),
        )
        self.assertEqual(done, [True])

    def test_build_session_context(self):
        history = [("user", "问题A"), ("assistant", "回答A")]
        context = build_session_context(history, "问题B")
        self.assertIn("用户: 问题A", context)
        self.assertIn("AI: 回答A", context)
        self.assertIn("【当前问题】", context)
        self.assertIn("问题B", context)

    def test_question_display_lines(self):
        history = [
            ("user", "普通问题"),
            ("assistant", "回答"),
            ("user", "[深度推理] 复杂问题"),
        ]
        lines = question_display_lines(history, [None, None, None])
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("1."))
        self.assertIn("[深度推理]", lines[1])

    def test_simple_keywords(self):
        keywords = simple_keywords("如何制定一个战略方案")
        self.assertIsInstance(keywords, list)
        self.assertTrue(all(isinstance(k, str) for k in keywords))

    def test_similar_crystal_pairs(self):
        class _Crystal:
            id = "C001"
            content = "晶体内容"

        engine = SimpleNamespace(
            parse_crystals=lambda: [_Crystal()],
            _simple_similarity=lambda a, b: 0.9,
        )
        pairs = similar_crystal_pairs(engine, "晶体内容")
        self.assertEqual(len(pairs), 1)
        self.assertAlmostEqual(pairs[0][0], 0.9)
        self.assertEqual(pairs[0][1].id, "C001")

    def test_parse_keyword_input(self):
        self.assertEqual(parse_keyword_input(" 战略 , 管理；AI "), ["战略", "管理", "AI"])
        self.assertEqual(parse_keyword_input(None), [])

    def test_run_gui_daily_plan(self):
        done = []
        with mock.patch("harness.services.DailyPlanner") as planner_cls:
            planner_cls.return_value.run.return_value = {"ok": True}
            run_gui_daily_plan(
                FakeEngine(),
                FakeAI(),
                mock.Mock(),
                lambda m, level="system": None,
                lambda s: None,
                ["关键词"],
                600,
                lambda: False,
                lambda data: None,
                lambda: done.append(True),
            )
        self.assertEqual(done, [True])

    def test_save_report_to_desktop(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_report_to_desktop(
                "问题",
                {"rounds": []},
                "老板版",
                "员工版",
                "新人版",
                "专家版",
                {},
                ai_client=None,
                log=lambda m, level="system": None,
                desktop_dir=Path(tmp),
            )
            for key in ("compressed", "original", "quick"):
                self.assertTrue(Path(paths[key]).exists(), key)

    def test_resolve_round_titles_first_fallback(self):
        sess_title, round_label = resolve_round_titles(
            True,
            "如何提升决策质量",
            "回答",
            ["已有标题"],
            lambda: FakeAI(),
            lambda m, level="system": None,
        )
        self.assertTrue(sess_title)
        self.assertIsInstance(round_label, str)

    def test_resolve_round_titles_non_first(self):
        sess_title, round_label = resolve_round_titles(
            False,
            "如何提升决策质量",
            "回答",
            [],
            lambda: FakeAI(),
            lambda m, level="system": None,
            [],
        )
        self.assertEqual(sess_title, "")
        self.assertIsInstance(round_label, str)

    def test_force_archive_holes(self):
        files = FakeFiles()
        logs = []
        count = force_archive_holes(
            files,
            [{"id": "H001", "content": "孔洞", "urgency": 0.9}],
            lambda m, level="system": logs.append(m),
        )
        self.assertEqual(count, 1)
        self.assertIn("PENDING-ARCHIVE-", files.data["pending"])
        self.assertTrue(logs)

    def test_run_single_deep_reasoning(self):
        progress = []
        result = run_single_deep_reasoning(
            FakeEngine(),
            FakeAI(),
            "sk-test",
            "问题",
            lambda user_input: user_input,
            lambda percent, stage: progress.append((percent, stage)),
        )
        self.assertIn("【综合最终答案】", result)
        self.assertEqual(progress[-1][0], 100)

    def test_build_rumad_status_text(self):
        if build_rumad_status_text is None:
            self.skipTest("GUI parts are not shipped in the public build")
        disabled = build_rumad_status_text(False, None)
        self.assertIn("❌ 禁用", disabled)
        debate = SimpleNamespace(
            get_rumad_stats=lambda: {
                "total_actions": 5,
                "q_table_size": 8,
                "last_reward": 0.5,
            }
        )
        enabled = build_rumad_status_text(True, debate)
        self.assertIn("✅ 启用", enabled)
        self.assertIn("动作数: 5", enabled)

    def test_vote_role(self):
        score, label = vote_role(FakeEngine(), "radical", True)
        self.assertEqual(score, 0.8)
        self.assertEqual(label, "支持")

    def test_parse_and_confirm_pending_card(self):
        files = FakeFiles()
        files.data["pending"] = (
            "## PENDING-20260811-001\n"
            "- 标题：测试标题\n"
            "- 内容：测试内容\n"
        )
        block, content, _ = parse_pending_card_block(
            files,
            "PENDING-20260811-001",
        )
        self.assertTrue(block)
        self.assertEqual(content, "测试标题")
        result = confirm_pending_card_with_content(
            files,
            FakeEngine(),
            "PENDING-20260811-001",
            "新内容",
            similar_fn=lambda content: [],
        )
        self.assertTrue(result["ok"])
        self.assertNotIn("PENDING-20260811-001", files.data["pending"])

    def test_build_pending_card_view_data(self):
        files = FakeFiles()
        files.data["pending"] = (
            "## PENDING-20260811-001\n"
            "- 类型：晶体候选\n"
            "- 标题：测试标题\n"
            "- 来源：AI生成\n"
        )
        cards = build_pending_card_view_data(files)
        self.assertEqual(cards[0]["id"], "PENDING-20260811-001")
        self.assertEqual(cards[0]["title"], "测试标题")

    def test_wisdom_commons_display(self):
        lines = wisdom_commons_display(FakeEngine())
        self.assertTrue(any("C001" in line for line in lines))

    def test_update_gui_files(self):
        files = FakeFiles()
        engine = FakeEngine()
        update_gui_files(
            files,
            engine,
            FakeConfig(),
            {
                "report_summary": "完成",
                "new_crystals": [
                    {
                        "id": "C001",
                        "content": "新晶体",
                        "links": [],
                    }
                ],
                "pending_cards": [],
            },
            lambda config, cid, content: True,
            lambda card: True,
        )
        self.assertEqual(len(engine.crystals), 1)
        self.assertIn("晶体总数", files.data["state"])


if __name__ == "__main__":
    unittest.main()
