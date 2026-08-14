import unittest

from external.ai_client import AIClient
from data.storage import FileIO
from harness.engine import CrystalEngine
from harness.processors.debate import DebateEngine, DebateRole


ROLES = [
    {"key": "radical", "name": "激进者", "instruction": "攻击默认前提，给出颠覆性方案。"},
    {"key": "conservative", "name": "保守者", "instruction": "风险优先，给出稳健方案。"},
    {"key": "structural", "name": "结构主义者", "instruction": "从已有晶体中寻找同构案例。"},
    {"key": "judge", "name": "大法官", "instruction": "依据晶体与原则做出终审裁决。"},
    {"key": "spokesperson", "name": "首席发言人", "instruction": "将辩论结论转化为清晰陈述。"},
    {"key": "lark", "name": "百灵鸟", "instruction": "补充外部世界知识。"},
    {"key": "pilgrim", "name": "取经者", "instruction": "锚定长期愿景与价值观。"},
    {"key": "strategist", "name": "奇谋者", "instruction": "捕捉机会窗口，敢押注非常规路径。"},
]


def common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


class TestPromptCachePrefix(unittest.TestCase):
    def setUp(self):
        engine = CrystalEngine(FileIO())
        self.debate = DebateEngine(
            AIClient(),
            engine,
            list(ROLES),
            log=lambda message, level="system": None,
            progress_callback=None,
        )
        self.crystal_context = "注意力晶体样本。" * 120
        self.evidence_context = "【证据包】[E001] 可核验证据。" * 60

    def _systems(self, round_num: int, external_brief: str):
        return [
            self.debate._role_system(
                DebateRole(**role),
                self.crystal_context,
                is_reflection=False,
                external_brief=external_brief,
                round_num=round_num,
                arbitration="仲裁意见" if round_num >= 1 else "",
            )
            for role in ROLES
        ]

    def test_cross_role_shared_prefix_is_long(self):
        systems = self._systems(0, external_brief="角色简报。" * 80)
        shared = systems[0]
        for system in systems[1:]:
            shared = shared[:common_prefix_len(shared, system)]
        self.assertGreater(len(shared), 1000)
        self.assertNotIn("激进者", shared)
        self.assertNotIn("保守者", shared)

    def test_same_role_across_rounds_keeps_long_prefix(self):
        role = DebateRole(**ROLES[0])
        s0 = self.debate._role_system(
            role,
            self.crystal_context,
            external_brief="角色简报。" * 80,
            round_num=0,
        )
        s1 = self.debate._role_system(
            role,
            self.crystal_context,
            external_brief="角色简报。" * 80,
            round_num=1,
            arbitration="仲裁意见",
        )
        s2 = self.debate._role_system(
            role,
            self.crystal_context,
            external_brief="角色简报。" * 80,
            round_num=2,
            arbitration="仲裁意见",
        )
        self.assertGreater(common_prefix_len(s0, s1), 1500)
        self.assertGreater(common_prefix_len(s1, s2), 1500)
        self.assertIn("【角色锚点】", s2)
        self.assertNotIn("【角色锚点】", s2[:common_prefix_len(s0, s1)])

    def test_fallback_system_keeps_shared_prefix(self):
        system = self.debate._fallback_system(DebateRole(**ROLES[0]))
        self.assertTrue(system.startswith("你是认知晶体树辩论引擎的成员。"))
        self.assertIn("【角色身份】你是认知晶体树辩论引擎中的【激进者】。", system)


if __name__ == "__main__":
    unittest.main()
