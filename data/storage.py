#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from core.models import HealthCheckResult
from governance.config import Config

class FileIO:
    @staticmethod
    def resolve(path: str) -> Path:
        return Config.get_path(path) if path in Config.PATHS else Config.DATA_ROOT / path

    @staticmethod
    def read(path: str) -> str:
        full = FileIO.resolve(path)
        if not full.exists():
            return ""
        with open(full, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write(path: str, content: str) -> None:
        full = FileIO.resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def append(path: str, content: str) -> None:
        full = FileIO.resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        with open(full, "a", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def exists(path: str) -> bool:
        return FileIO.resolve(path).exists()

    @staticmethod
    def ensure_directories() -> None:
        for dir_name in Config.DIRECTORIES:
            (Config.DATA_ROOT / dir_name).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def read_fingerprint() -> Dict[str, Any]:
        """读取认知指纹 JSON"""
        content = FileIO.read("fingerprint")
        if not content:
            return {
                "fingerprint": {
                    "risk_tolerance": 0.5,
                    "innovation_preference": 0.5,
                    "decisiveness": 0.5,
                    "preferred_role": "structural",
                    "role_adoption_history": {},
                    "conflict_resolution_style": "integrative",
                    "attention_span": 0.5,
                    "context_preference": 3,
                    "reasoning_style": "balanced",
                    "analogy_preference": "balanced",
                    "output_style": "balanced",
                    "language_style": {
                        "wenbai_ratio": "balanced",
                        "metaphor_preference": "nature",
                        "rhythm_preference": "balanced",
                        "cultural_roots": ["儒家", "道家"]
                    },
                    "last_updated": datetime.now().isoformat(),
                    "total_interactions": 0,
                    "confidence": 0.3,
                    "evolution_log": []
                },
                "extraction_metadata": {
                    "last_extraction": None,
                    "messages_analyzed": 0,
                    "debates_analyzed": 0,
                    "crystals_created": 0,
                    "version": "1.0"
                }
            }
        try:
            data = json.loads(content)
            # 确保 fingerprint 存在且包含 language_style
            if "fingerprint" not in data:
                data["fingerprint"] = {}
            fp = data["fingerprint"]
            if "language_style" not in fp:
                fp["language_style"] = {
                    "wenbai_ratio": "balanced",
                    "metaphor_preference": "nature",
                    "rhythm_preference": "balanced",
                    "cultural_roots": ["儒家", "道家"]
                }
            # 同时确保其他可能缺失的字段
            fp.setdefault("reasoning_style", "balanced")
            fp.setdefault("analogy_preference", "balanced")
            fp.setdefault("output_style", "balanced")
            return data
        except json.JSONDecodeError:
            return {
                "fingerprint": {
                    "risk_tolerance": 0.5,
                    "innovation_preference": 0.5,
                    "decisiveness": 0.5,
                    "preferred_role": "structural",
                    "role_adoption_history": {},
                    "conflict_resolution_style": "integrative",
                    "attention_span": 0.5,
                    "context_preference": 3,
                    "reasoning_style": "balanced",
                    "analogy_preference": "balanced",
                    "output_style": "balanced",
                    "language_style": {
                        "wenbai_ratio": "balanced",
                        "metaphor_preference": "nature",
                        "rhythm_preference": "balanced",
                        "cultural_roots": ["儒家", "道家"]
                    },
                    "last_updated": datetime.now().isoformat(),
                    "total_interactions": 0,
                    "confidence": 0.3,
                    "evolution_log": []
                },
                "extraction_metadata": {
                    "last_extraction": None,
                    "messages_analyzed": 0,
                    "debates_analyzed": 0,
                    "crystals_created": 0,
                    "version": "1.0"
                }
            }

    @staticmethod
    def write_fingerprint(data: Dict[str, Any]) -> None:
        """写入认知指纹 JSON"""
        FileIO.write("fingerprint", json.dumps(data, ensure_ascii=False, indent=2))

    @staticmethod
    def ensure_default_files() -> None:
        defaults = {
            "principles": "# 核心操作原则\n\n（待补充）",
            "ai_instructions": "# AI协作者指令\n\n（待补充）",
            "crystals": "# 晶体卡片库\n\n| ID | 内容 | 链接 |\n|----|------|------|\n",
            "holes": "# 孔洞分层\n\n## 第一层：核心孔洞\n\n| ID | 内容 | 紧迫度 |\n|----|------|--------|\n",
            "state": "# 系统状态快照\n\n（初始状态）",
            "change_log": "# 系统变更记录\n\n",
            "pending": "# PENDING 待确认卡片\n\n",
            "search_cache": "# 搜索摘要\n\n",
            "layer_state": json.dumps({"layers": {}, "heat_map": {}, "last_accessed": {}, "manual_override": {}}, ensure_ascii=False, indent=2),
            "hole_progress": json.dumps({}, ensure_ascii=False, indent=2),
            "external_cache": json.dumps({}, ensure_ascii=False, indent=2),
            "task_cards": "[]",
            "roles": json.dumps({
                "radical": {"name": "激进者", "instruction": "攻击默认前提，假设现有框架是错的，给出颠覆性方案。"},
                "conservative": {"name": "保守者", "instruction": "风险优先，假设资源有限，给出最可落地的稳健方案。"},
                "structural": {"name": "结构主义者", "instruction": "从已有晶体中寻找同构案例，用类比生成方案。"},
                "judge": {"name": "大法官","instruction": "以晶体卡片、核心操作原则和资源约束为准绳，做出终审裁决。必须明确引用依据（晶体ID、原则条款或约束条件），不得凭直觉判案。"},
                "spokesperson": {"name": "首席发言人","instruction": "将内部辩论结论转化为清晰、简洁、无歧义的对外陈述。遵循降维（通俗化）、定调（不超过3条核心信息）、检验（老板读前100字能决策）三原则。"},
                "lark": {"name": "百灵鸟","instruction": "见多识广的通用智能体，从外部世界（学术、产业、政策、跨学科）补充知识，打破信息茧房。在第二轮登场。"},
                "pilgrim": {"name": "取经者","instruction": "以长期愿景和核心价值观为锚，防止短期利益或局部优化偏离最终使命。评估方案的可持续性和道德一致性。"},
                "strategist": {"name": "奇谋者","instruction": "善于洞察人心、把握时机，敢押注非常规路径，捕捉机会窗口。评估方案能否借力打力、以奇制胜。"},
                "statesman": {"name": "延安智者","instruction": "坚持调查研究，不唯上、不唯书、只唯实。从全局矛盾和主要矛盾切入，提出实事求是、可落地的综合方略。"}              
            }, ensure_ascii=False, indent=2)
        }
        # 写入所有默认文本文件
        for key, content in defaults.items():
            if not FileIO.exists(key):
                FileIO.write(key, content)

        # ===== Day 0 新增：pareto_frontier.json（帕累托前沿跟踪） =====
        pareto_path = Config.DATA_ROOT / "系统日志" / "pareto_frontier.json"
        if not pareto_path.exists():
            with open(pareto_path, "w", encoding="utf-8") as f:
                json.dump({
                    "configs": {
                        "PROFILE_HIGH_ACCURACY": {"accuracy": 0.9, "cost": 0.3, "latency": 0.2},
                        "PROFILE_BALANCED": {"accuracy": 0.7, "cost": 0.2, "latency": 0.15},
                        "PROFILE_ECONOMY": {"accuracy": 0.5, "cost": 0.1, "latency": 0.1}
                    },
                    "history": []
                }, f, ensure_ascii=False, indent=2)

        # ===== Day 0 新增：灵感池.json（灵感熔炉数据） =====
        insp_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
        if not insp_path.exists():
            with open(insp_path, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "id": "INSP-001",
                        "source": "对话",
                        "content": "初始灵感：将‘八道防线’与‘沉思式反思’融合，形成免疫+智慧的协同效应",
                        "status": "待筛选",
                        "created_at": datetime.now().isoformat()
                    }
                ], f, ensure_ascii=False, indent=2)
            
class HealthChecker:
    @staticmethod
    def run() -> List[HealthCheckResult]:
        results = []
        for directory in Config.DIRECTORIES:
            path = Config.DATA_ROOT / directory
            if not path.exists():
                results.append(HealthCheckResult("warning", directory, "目录不存在", "启动初始化会自动创建"))
        for key in Config.PATHS:
            path = Config.get_path(key)
            if not path.exists():
                results.append(HealthCheckResult("warning", Config.PATHS[key], "文件不存在", "启动初始化会按默认模板创建"))
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                results.append(HealthCheckResult("error", Config.PATHS[key], "文件不是有效 UTF-8 编码", "请先备份后统一转为 UTF-8"))
                continue
            if key in ("layer_state", "hole_progress", "external_cache", "task_cards"):
                try:
                    json.loads(text or "{}")
                except json.JSONDecodeError as exc:
                    results.append(HealthCheckResult("error", Config.PATHS[key], f"JSON 解析失败: {exc}", "请检查逗号、括号和引号"))
            if key == "crystals" and text and "| ID | 内容 | 链接 |" not in text:
                results.append(HealthCheckResult("warning", Config.PATHS[key], "晶体卡片表头缺失", "请确认 Markdown 表格结构"))
            if key == "holes" and text and "| ID | 内容 | 紧迫度 |" not in text:
                results.append(HealthCheckResult("warning", Config.PATHS[key], "孔洞表头缺失", "请确认 Markdown 表格结构"))
        return results


class DBManager:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Config.get_db_path()
        self._init_db()
        
    def _connect(self):
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.row_factory = sqlite3.Row
                return conn
            except sqlite3.OperationalError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))
                continue

    def _init_db(self):
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TIMESTAMP, updated_at TIMESTAMP, messages TEXT)''')
            conn.commit()

    def _safe_session_name(self, name: str, created_at: datetime = None) -> str:
        cleaned = (name or "").strip()
        if not cleaned or set(cleaned) <= {"?"} or "\ufffd" in cleaned:
            ts = created_at or datetime.now()
            return f"新会话 {ts.strftime('%H:%M')}"
        return cleaned

    def create_session(self, session_id: str, name: str):
        name = self._safe_session_name(name)
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('INSERT INTO sessions (id, name, created_at, updated_at, messages) VALUES (?,?,?,?,?)', (session_id, name, now, now, json.dumps([])))
            conn.commit()

    def update_session(self, session_id: str, messages: List, name: str = None):
        """
        更新会话消息，消息元素可以是 tuple (role, content) 或 dict {role, content, label}
        自动转换为统一格式（包含 label 字段）
        """
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            if name:
                name = self._safe_session_name(name)
                cursor.execute('UPDATE sessions SET name = ?, updated_at = ? WHERE id = ?',
                               (name, datetime.now().isoformat(), session_id))
            else:
                cursor.execute('UPDATE sessions SET updated_at = ? WHERE id = ?',
                               (datetime.now().isoformat(), session_id))
            # 统一转换为带 label 的 dict
            new_msgs = []
            for item in messages:
                if isinstance(item, dict):
                    # 如果已经是 dict，确保有 label 字段
                    new_msgs.append({
                        "role": item.get("role", ""),
                        "content": item.get("content", ""),
                        "label": item.get("label")
                    })
                else:
                    # 假定是 tuple (role, content)
                    role, content = item[0], item[1]
                    new_msgs.append({"role": role, "content": content, "label": None})
            cursor.execute('UPDATE sessions SET messages = ? WHERE id = ?',
                           (json.dumps(new_msgs, ensure_ascii=False), session_id))
            conn.commit()

    def get_session(self, session_id: str):
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, messages FROM sessions WHERE id = ?', (session_id,))
            row = cursor.fetchone()
        if row:
            name, messages_json = row
            messages = json.loads(messages_json)
            history = []
            labels = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                label = msg.get("label")  # 可能为 None
                history.append((role, content))
                labels.append(label)
            return name, history, labels
        return None, [], []

    def list_sessions(self):
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, updated_at FROM sessions ORDER BY updated_at DESC')
            return cursor.fetchall()

    def delete_session(self, session_id: str):
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
            conn.commit()

    def rename_session(self, session_id: str, new_name: str):
        new_name = self._safe_session_name(new_name)
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE sessions SET name = ?, updated_at = ? WHERE id = ?', (new_name, datetime.now().isoformat(), session_id))
            conn.commit()

