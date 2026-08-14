"""Atomic, reversible patch storage."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class PatchStore:
    """JSON document store with an SQLite patch journal."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.data_path = self.root / "vault" / "state.json"
        self.db_path = self.root / "系统日志" / "changelog" / "patches.db"
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_path.exists():
            _atomic_write_json(self.data_path, {})
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS patches (
                    id TEXT PRIMARY KEY,
                    patch_type TEXT,
                    target TEXT,
                    pre_hash TEXT,
                    status TEXT,
                    created_at TEXT
                )
                """
            )

    def _read_data(self) -> Dict[str, Any]:
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    def _write_data(self, data: Dict[str, Any]) -> None:
        _atomic_write_json(self.data_path, data)

    def pre_condition_hash(self, key: Optional[str] = None) -> str:
        data = self._read_data()
        payload = data.get(key) if key is not None else data
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _log(self, patch: "JSONPatch") -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO patches
                (id, patch_type, target, pre_hash, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    patch.patch_id,
                    patch.patch_type,
                    patch.target,
                    patch.pre_condition_hash,
                    patch.status,
                    datetime.now().isoformat(),
                ),
            )

    def _mark_rolled_back(self, patch_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE patches SET status = ? WHERE id = ?",
                ("rolled_back", patch_id),
            )

    def list_patches(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM patches ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]


class JSONPatch:
    """Patch object that owns its apply/rollback behavior."""

    def __init__(
        self,
        store: PatchStore,
        key: str,
        new_value: Any,
        patch_type: str = "data",
    ) -> None:
        self.store = store
        self.target = key
        self.new_value = new_value
        self.patch_type = patch_type
        self.patch_id = uuid.uuid4().hex[:16]
        self.pre_condition_hash = store.pre_condition_hash(key)
        self.old_value: Any = None
        self.had_old = False
        self.status = "pending"

    def apply(self) -> bool:
        if self.status != "pending":
            return False
        if self.store.pre_condition_hash(self.target) != self.pre_condition_hash:
            raise ValueError("precondition hash mismatch")
        data = self.store._read_data()
        self.had_old = self.target in data
        self.old_value = data.get(self.target)
        data[self.target] = self.new_value
        self.store._write_data(data)
        self.status = "applied"
        self.store._log(self)
        return True

    def rollback(self) -> bool:
        if self.status != "applied":
            return False
        data = self.store._read_data()
        if self.had_old:
            data[self.target] = self.old_value
        else:
            data.pop(self.target, None)
        self.store._write_data(data)
        self.store._mark_rolled_back(self.patch_id)
        self.status = "rolled_back"
        return True

    def describe(self) -> str:
        return f"{self.patch_type} patch on {self.target} [{self.status}]"
