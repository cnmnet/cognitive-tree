import unittest

from core.interfaces import EvolutionStrategy
from evolution.strategy import GodelStrategy, MetaStrategy
from harness.strategy import HebbianStrategy, RUMADStrategy
from access.factory import build_evolution_strategies


class _FakeGodel:
    def run_evolution_cycle(self, role_name="radical"):
        return {"cycle": role_name}

    def run_recursive_evolution_cycle(self):
        return {"recursive": True}


class _FakeMeta:
    def run_all_primitives(self):
        return {"primitives": 3}

    def run_dual_loop(self, max_merges=2, max_grafts=1):
        return {"dual": max_merges + max_grafts}


class _FakeRumad:
    def __init__(self):
        self.last_reward = 0.5

    def select_action(self, state_key, actions, round_num=1):
        return actions[0] if actions else None

    def update_with_result(self, previous_answers, current_answers,
                           previous_audit, current_audit):
        self.last_reward = 0.8

    def get_stats(self):
        return {"total_actions": 1}


class _FakeEngine:
    def record_hebbian_reward(self, kind, crystal_ids=None, role_keys=None,
                              reward=None, question=None, task_type=None,
                              context=None):
        return 0.7


class TestEvolutionStrategy(unittest.TestCase):
    def test_adapters_satisfy_protocol(self):
        godel = GodelStrategy(_FakeGodel())
        meta = MetaStrategy(_FakeMeta())
        rumad = RUMADStrategy(_FakeRumad())
        hebbian = HebbianStrategy(_FakeEngine())
        for strategy in (godel, meta, rumad, hebbian):
            self.assertIsInstance(strategy, EvolutionStrategy)

    def test_runs_return_dicts(self):
        self.assertEqual(
            GodelStrategy(_FakeGodel()).run({"role_name": "conservative"}),
            {"cycle": "conservative"},
        )
        self.assertEqual(
            GodelStrategy(_FakeGodel()).run({"action": "recursive"}),
            {"recursive": True},
        )
        self.assertEqual(
            MetaStrategy(_FakeMeta()).run({}),
            {"primitives": 3},
        )
        self.assertEqual(
            MetaStrategy(_FakeMeta()).run({"action": "dual_loop"}),
            {"dual": 3},
        )
        self.assertEqual(
            RUMADStrategy(_FakeRumad()).run(
                {
                    "state_key": "s",
                    "available_actions": [("激进者", "保守者")],
                }
            ),
            {"action": ("激进者", "保守者")},
        )
        self.assertEqual(
            HebbianStrategy(_FakeEngine()).run({"kind": "adopt"}),
            {"rate": 0.7},
        )

    def test_factory_builds_four_strategies(self):
        strategies = build_evolution_strategies(
            _FakeEngine(),
            meta_layer=_FakeMeta(),
            rumad=_FakeRumad(),
            godel=_FakeGodel(),
        )
        names = {s.name for s in strategies}
        self.assertEqual(names, {"godel", "meta", "rumad", "hebbian"})
