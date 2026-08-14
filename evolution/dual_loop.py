"""Dual-loop runner: stage -> fast filter -> execute -> slow judge -> verify."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from governance.config import Config

from .fast_loop import FastLoop
from .operators import OperatorExecutor, build_patch
from .slow_loop import SlowLoop
from .staging_pool import StagingPool


class DualLoopRunner:
    def __init__(self, engine: Any, log_callback=None):
        self.engine = engine
        self.log = log_callback or (lambda msg, level="system": None)
        self.executor = OperatorExecutor(engine, log_callback=log_callback)
        self.staging = StagingPool()
        self.fast_loop = FastLoop(min_score=65.0)
        self.slow_loop = SlowLoop(min_improvement=0.5, metrics=["improvement"])

    def _conflict_patches(self, limit: int = 2) -> List[Dict[str, Any]]:
        patches = []
        try:
            conflicts = self.engine.detect_conflicts(method="auto")[:limit]
            for conflict in conflicts:
                a = getattr(conflict, "a", None) or conflict.get("a")
                b = getattr(conflict, "b", None) or conflict.get("b")
                if not a or not b:
                    continue
                reason = getattr(conflict, "reason", "") or (conflict.get("reason", "") if isinstance(conflict, dict) else "")
                patches.append({
                    **build_patch("CRYSTAL_MERGE", a, {"a": a, "b": b, "reason": reason}),
                    "id": f"merge_{a}_{b}",
                    "score": 75.0,
                })
        except Exception as e:
            self.log(f"⚠️ 双环冲突采集失败：{e}", "warning")
        return patches

    def _inspiration_patches(self, limit: int = 1) -> List[Dict[str, Any]]:
        patches = []
        try:
            pool_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
            if not pool_path.exists():
                return patches
            pool = json.loads(pool_path.read_text(encoding="utf-8"))
            items = pool if isinstance(pool, list) else pool.get("items", [])
            for item in items:
                if len(patches) >= limit:
                    break
                content = item.get("content", "").strip()
                importance = float(item.get("importance", item.get("priority", 0)) or 0)
                if content and importance >= 0.7:
                    patches.append({
                        **build_patch("CRYSTAL_ADD", "new", {"content": content}),
                        "id": f"graft_{item.get('id', 'insp')}",
                        "score": 70.0,
                    })
        except Exception as e:
            self.log(f"⚠️ 双环灵感采集失败：{e}", "warning")
        return patches

    def run_once(self, max_merges: int = 2, max_grafts: int = 1) -> Dict[str, Any]:
        baseline_conflicts = len(self.engine.detect_conflicts(method="auto"))
        baseline_crystals = len(self.engine.parse_crystals())

        drafts = self._conflict_patches(max_merges) + self._inspiration_patches(max_grafts)
        if not drafts:
            return {
                "executed": 0,
                "rolled_back": 0,
                "skipped": 0,
                "message": "无可执行候选",
                "verify": self.engine.verify_dual_loop(),
            }

        staged_ids = []
        for draft in drafts:
            self.staging.submit(draft)
            staged_ids.append(draft.get("id", ""))

        passed = [d for d in self.staging.fetch_candidates(limit=len(drafts)) if self.fast_loop.evaluate(d).get("passed")]
        executed = 0
        records = []
        for draft in passed:
            patch = {k: v for k, v in draft.items() if k not in ("id", "score")}
            result = self.executor.apply(patch)
            if result.get("ok"):
                executed += 1
                records.append(result["record"])
                self.log(f"✅ 双环执行算子：{patch['patch_type']} -> {patch.get('target')}", "success")
            else:
                self.log(f"⚠️ 双环算子执行失败：{result.get('reason')}", "warning")

        current_conflicts = len(self.engine.detect_conflicts(method="auto"))
        current_crystals = len(self.engine.parse_crystals())
        improvement = 0.0
        merged = [r for r in records if r["patch_type"] == "CRYSTAL_MERGE"]
        grafted = [r for r in records if r["patch_type"] == "CRYSTAL_ADD"]
        if merged:
            improvement = baseline_conflicts - current_conflicts
        elif grafted:
            improvement = current_crystals - baseline_crystals

        decision = self.slow_loop.decide({"improvement": 0.0}, {"improvement": improvement})
        rolled_back = 0
        if decision.get("rollback") and records:
            for record in reversed(records):
                if self.executor.rollback(record):
                    rolled_back += 1
            self.log("↩️ 双环慢环判定无改善，已回滚本次进化", "warning")

        verify = self.engine.verify_dual_loop()
        return {
            "executed": executed,
            "rolled_back": rolled_back,
            "skipped": len(drafts) - len(passed),
            "improvement": round(improvement, 3),
            "baseline": {"conflicts": baseline_conflicts, "crystals": baseline_crystals},
            "current": {"conflicts": current_conflicts, "crystals": current_crystals},
            "verify": verify,
        }
