import time
import unittest

from evolution.fast_loop import FastLoop
from evolution.governance import auditor, debate_on_config, proposal
from evolution.operators import graft, merge, promote, prune
from evolution.slow_loop import SlowLoop
from evolution.staging_pool import StagingPool


class TestEvolution(unittest.TestCase):
    def test_staging_pool(self):
        pool = StagingPool(ttl_seconds=0.01)
        pool.submit({"id": "d1", "target": "roles", "score": 80})
        self.assertTrue(pool.conflict_check({"target": "roles"}))
        self.assertTrue(pool.fetch_candidates())
        time.sleep(0.02)
        self.assertEqual(pool.fetch_candidates(), [])

    def test_fast_loop(self):
        loop = FastLoop(min_score=65)
        self.assertTrue(loop.evaluate({"score": 80})["passed"])
        self.assertFalse(loop.evaluate({"score": 30})["passed"])

    def test_slow_loop(self):
        loop = SlowLoop(min_improvement=0.03)
        result = loop.decide({"jaccard": 0.2}, {"jaccard": 0.2})
        self.assertTrue(result["rollback"])

    def test_operators(self):
        self.assertEqual(prune(["C001"])[0]["patch_type"], "CRYSTAL_DELETE")
        self.assertEqual(promote(["C001"])[0]["patch_type"], "LAYER_UPDATE")
        self.assertEqual(merge([("C001", "C002")])[0]["patch_type"], "CRYSTAL_MERGE")
        self.assertEqual(graft("新晶体")["patch_type"], "CRYSTAL_ADD")

    def test_governance(self):
        p = proposal({"key": "roles", "risks": []})
        d = debate_on_config(p)
        a = auditor(d)
        self.assertTrue(a["accepted"])


if __name__ == "__main__":
    unittest.main()
