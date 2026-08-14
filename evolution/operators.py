"""Executable patch operators with rollback support."""

from __future__ import annotations

import re
from typing import Any, Dict, List


def build_patch(patch_type: str, target: str, payload: Any) -> Dict[str, Any]:
    return {
        "patch_type": patch_type,
        "target": target,
        "payload": payload,
    }


def prune(crystal_ids: List[str]) -> List[Dict[str, Any]]:
    return [build_patch("CRYSTAL_DELETE", cid, {"reason": "prune"}) for cid in crystal_ids]


def promote(crystal_ids: List[str]) -> List[Dict[str, Any]]:
    return [build_patch("LAYER_UPDATE", cid, {"layer": "L1"}) for cid in crystal_ids]


def merge(pairs: List[tuple]) -> List[Dict[str, Any]]:
    return [build_patch("CRYSTAL_MERGE", f"{a}+{b}", {"a": a, "b": b}) for a, b in pairs]


def graft(content: str) -> Dict[str, Any]:
    return build_patch("CRYSTAL_ADD", "new", {"content": content})


class OperatorExecutor:
    """把 patch 真正执行到晶体树，并支持回滚。"""

    def __init__(self, engine: Any, log_callback=None):
        self.engine = engine
        self.log = log_callback or (lambda msg, level="system": None)

    def _find_crystal(self, crystal_id: str):
        for crystal in self.engine.parse_crystals():
            if crystal.id == crystal_id:
                return crystal
        return None

    def _next_crystal_id(self) -> str:
        existing = [c.id for c in self.engine.parse_crystals()]
        nums = [int(m.group(1)) for cid in existing for m in [re.search(r"C(\d+)", cid)] if m]
        return f"C{max(nums, default=0) + 1:03d}"

    def apply(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        ptype = patch.get("patch_type")
        target = patch.get("target")
        payload = patch.get("payload", {}) or {}
        record = {
            "patch_type": ptype,
            "target": target,
            "payload": payload,
            "status": "applied",
            "before": None,
            "result": None,
        }
        try:
            if ptype == "CRYSTAL_DELETE":
                crystal = self._find_crystal(target)
                if crystal is None:
                    return {"ok": False, "reason": f"晶体 {target} 不存在"}
                record["before"] = {
                    "crystal_id": crystal.id,
                    "content": crystal.content,
                    "links": list(crystal.links or []),
                    "layer": getattr(crystal, "layer", None),
                }
                record["result"] = self.engine.delete_crystal(target)
            elif ptype == "CRYSTAL_ADD":
                crystal_id = target if target and target != "new" else self._next_crystal_id()
                record["target"] = crystal_id
                record["result"] = self.engine.create_crystal(
                    crystal_id=crystal_id,
                    content=str(payload.get("content", "")),
                    links=list(payload.get("links", []) or []),
                    source="evolution_operator",
                )
            elif ptype == "LAYER_UPDATE":
                crystal = self._find_crystal(target)
                if crystal is None:
                    return {"ok": False, "reason": f"晶体 {target} 不存在"}
                state = self.engine.load_layer_state()
                record["before"] = {
                    "crystal_id": target,
                    "layer_state": state,
                }
                layers = state.setdefault("layers", {})
                layers[target] = payload.get("layer", "L1")
                self.engine.save_layer_state(state)
                record["result"] = True
            elif ptype == "CRYSTAL_MERGE":
                a = payload.get("a")
                b = payload.get("b")
                ca = self._find_crystal(a)
                cb = self._find_crystal(b)
                if ca is None or cb is None:
                    return {"ok": False, "reason": "合并晶体不存在"}
                record["before"] = {
                    "a": {"crystal_id": a, "content": ca.content, "links": list(ca.links or [])},
                    "b": {"crystal_id": b, "content": cb.content, "links": list(cb.links or [])},
                }
                merged_content = f"{ca.content}\n\n{cb.content}"
                merged_links = list(dict.fromkeys(list(ca.links or []) + list(cb.links or []) + [a, b]))
                self.engine.update_crystal_content(a, merged_content, merged_links)
                self.engine.delete_crystal(b)
                record["result"] = True
            else:
                return {"ok": False, "reason": f"未知算子: {ptype}"}
            self.engine.log_evolution_event("operator_executed", {
                "patch_type": ptype,
                "target": record["target"],
                "payload": payload,
                "ok": True,
            })
            return {"ok": True, "record": record}
        except Exception as e:
            return {"ok": False, "reason": str(e), "record": record}

    def rollback(self, record: Dict[str, Any]) -> bool:
        before = record.get("before")
        ptype = record.get("patch_type")
        if not before:
            return False
        try:
            if ptype == "CRYSTAL_DELETE":
                self.engine.create_crystal(
                    crystal_id=before["crystal_id"],
                    content=before["content"],
                    links=before["links"],
                    source="rollback",
                )
            elif ptype == "CRYSTAL_ADD":
                self.engine.delete_crystal(record.get("target", ""))
            elif ptype == "LAYER_UPDATE":
                self.engine.save_layer_state(before["layer_state"])
            elif ptype == "CRYSTAL_MERGE":
                self.engine.update_crystal_content(before["a"]["crystal_id"], before["a"]["content"], before["a"]["links"])
                self.engine.create_crystal(
                    crystal_id=before["b"]["crystal_id"],
                    content=before["b"]["content"],
                    links=before["b"]["links"],
                    source="rollback",
                )
            self.engine.log_evolution_event("operator_rolled_back", {"patch_type": ptype, "target": record.get("target")})
            return True
        except Exception:
            return False
