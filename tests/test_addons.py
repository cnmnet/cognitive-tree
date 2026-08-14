import unittest

from addons.base import get, list_scenes, load_addons


class TestAddons(unittest.TestCase):
    def setUp(self):
        load_addons()

    def test_load_composition_scene(self):
        scenes = list_scenes()
        self.assertTrue(any(s["scene_id"] == "composition" for s in scenes))
        addon = get("composition")
        self.assertIsNotNone(addon)
        self.assertEqual(addon.scene.name, "作文因材施教")
        self.assertEqual(addon.scene.report_schema["compressed"]["max_chars"], 400)

    def test_composition_compress_hook(self):
        addon = get("composition")
        full = (
            "这是一段很长的铺垫。" * 100
            + "## 结论\n选B。\n"
            + "## 理由\n现金流更快。\n"
            + "## 下一步\n先试点再规模化。\n"
            + "## 止损\n毛利率低于15%止损。"
        )
        compressed = addon.hook("on_report_compressed", full)
        self.assertLessEqual(len(compressed), 400)
        for section in ("结论", "理由", "下一步"):
            self.assertIn(section, compressed)

    def test_composition_feedback_hook_requires_engine(self):
        addon = get("composition")
        result = addon.hook("on_user_feedback", "adopt", engine=None)
        self.assertFalse(result["ok"])

    def test_list_scenes(self):
        self.assertTrue(any(s["scene_id"] == "composition" for s in list_scenes()))

    def test_composition_review_returns_five_versions(self):
        from addons.composition.review import review_essay

        class _FakeAI:
            def chat_json(self, prompt, temperature=0.3, **kwargs):
                return {
                    "student_version": "先改开头的动作描写",
                    "parent_version": "在家练三个动词",
                    "teacher_version": "详略失当",
                    "expert_version": "提取线索不足",
                    "growth_version": "本周练比喻",
                }

        result = review_essay(
            "那天，我第一次学骑自行车。",
            [{"name": "A", "profile": "基础扎实"}],
            _FakeAI(),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["versions"]), 5)
        self.assertIn("先改开头的动作描写", result["versions"]["学生版"])

    def test_composition_review_missing_versions_fallback(self):
        from addons.composition.review import normalize_review

        result = normalize_review({"student_version": "只有学生版"})
        self.assertFalse(result["ok"])
        self.assertIn("家长版", result["missing"])
        self.assertIn("待补充", result["versions"]["家长版"])

    def test_composition_review_empty_essay(self):
        from addons.composition.review import review_essay

        result = review_essay("", [], None)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
