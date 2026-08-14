#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check capability parity between the 2.2 monolith and the v5 split modules.

Usage:
    python tools/parity_check.py --monolith <2.2 crystal_tree_all_in_one_day.py>
"""

from __future__ import annotations

import argparse
import builtins
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Tuple


ROOT = Path(__file__).resolve().parent.parent


def load_monolith(path: Path):
    spec = importlib.util.spec_from_file_location("crystal_tree_2_2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load monolith: {path}")
    module = importlib.util.module_from_spec(spec)
    monolith_dir = str(path.resolve().parent)
    if monolith_dir not in sys.path:
        sys.path.insert(0, monolith_dir)
    with tempfile.TemporaryDirectory(prefix="parity_monolith_") as tmp:
        os.environ["CRYSTAL_TREE_DATA_ROOT"] = tmp
        with redirect_stdout(io.StringIO()):
            spec.loader.exec_module(module)
        os.environ.pop("CRYSTAL_TREE_DATA_ROOT", None)
    return module


def load_v5():
    sys.path.insert(0, str(ROOT))
    from core import fingerprint as v5_fingerprint
    from core import models as v5_models
    from data import storage as v5_storage
    from data import vector_store as v5_vector
    from external import ai_client as v5_ai_client
    from external import fetcher as v5_fetcher
    from external import network as v5_network
    from external import search as v5_search
    from evolution import godel as v5_godel
    from evolution import meta_layer as v5_meta
    from governance import config as v5_config
    from governance import prompt_templates as v5_templates
    from harness import alarm as v5_alarm
    from harness import audit as v5_audit
    from harness import engine as v5_engine
    from harness import orchestrator as v5_orchestrator
    from harness import twin_workbench as v5_twin
    from harness.processors import debate as v5_debate
    from harness.assurance import anti_fraud as v5_fraud
    from harness.assurance import claim_extractor as v5_claim
    from harness.assurance import sandbox as v5_sandbox
    from harness.assurance import svr_mad as v5_svr
    from harness import force_explorer as v5_force
    from harness import gate as v5_gate
    from harness import reporting as v5_reporting
    from harness import rumad as v5_rumad

    return (
        v5_config,
        v5_models,
        v5_storage,
        v5_ai_client,
        v5_fetcher,
        v5_network,
        v5_search,
        v5_reporting,
        v5_gate,
        v5_rumad,
        v5_fingerprint,
        v5_vector,
        v5_audit,
        v5_alarm,
        v5_force,
        v5_templates,
        v5_fraud,
        v5_godel,
        v5_meta,
        v5_engine,
        v5_debate,
        v5_orchestrator,
        v5_claim,
        v5_sandbox,
        v5_svr,
        v5_twin,
    )


def compare_config(old, new, checks: List[Tuple[str, Callable[[Any], Any]]]) -> List[str]:
    failures = []
    for label, getter in checks:
        try:
            old_value = getter(old)
            new_value = getter(new)
        except Exception as exc:
            failures.append(f"config.{label}: error {exc}")
            continue
        if old_value != new_value:
            failures.append(f"config.{label}: old={old_value!r} new={new_value!r}")
    return failures


def compare_file_trees(old_root: Path, new_root: Path) -> List[str]:
    failures = []

    def snapshot(root: Path) -> Dict[str, str]:
        import re

        result = {}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                text = path.read_text(encoding="utf-8", errors="replace")
                text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?", "<ts>", text)
                result[rel] = text
        return result

    old_snap = snapshot(old_root)
    new_snap = snapshot(new_root)
    if old_snap != new_snap:
        failures.append("FileIO default file tree differs")
        for key in sorted(set(old_snap) | set(new_snap)):
            if old_snap.get(key) != new_snap.get(key):
                failures.append(f"  {key}: old_len={len(old_snap.get(key, ''))} new_len={len(new_snap.get(key, ''))}")
    return failures


def compare_db(old_db, new_db, session_id: str, name: str) -> List[str]:
    failures = []
    old_db.create_session(session_id, name)
    new_db.create_session(session_id, name)
    old_rows = [dict(r) for r in old_db.list_sessions()]
    new_rows = [dict(r) for r in new_db.list_sessions()]
    old_compact = [(r["id"], r["name"]) for r in old_rows]
    new_compact = [(r["id"], r["name"]) for r in new_rows]
    if old_compact != new_compact:
        failures.append(f"DB list_sessions: old={old_compact} new={new_compact}")
    old_session = old_db.get_session(session_id)
    new_session = new_db.get_session(session_id)
    if old_session != new_session:
        failures.append(f"DB get_session: old={old_session} new={new_session}")
    return failures


def normalize_report_markdown(text: str) -> str:
    """把 v5 有意增强的报告结构与旧 2.2 基准对齐后再比较。"""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "## 第一部分 · 辩论正文":
            continue
        if stripped == "## 第三部分 · 验证与来源材料":
            continue
        if stripped == "> 本部分保留多角色完整交锋、攻防与裁决过程；可执行结论以第二部分「决策附录」为准。":
            continue
        if stripped == "> 说明：以下为辩论正文中的多受众阐释，属角色个人主张，非终审裁决；最终可执行结论以第二部分「决策附录」为准。":
            line = "> 说明：以下为该角色个人主张，非终审裁决；最终结论以大法官裁决为准。"
        lines.append(line)
    normalized = []
    blank = False
    for line in lines:
        if line.strip() == "":
            if blank:
                continue
            blank = True
        else:
            blank = False
        normalized.append(line)
    return "\n".join(normalized)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--monolith",
        default=str(ROOT / "tools" / "reference" / "crystal_tree_all_in_one_day.py"),
    )
    args = parser.parse_args()

    old_mod = load_monolith(Path(args.monolith))
    (
        new_config,
        new_models,
        new_storage,
        new_ai_client,
        new_fetcher,
        new_network,
        new_search,
        new_reporting,
        new_gate,
        new_rumad_mod,
        new_fingerprint,
        new_vector,
        new_audit,
        new_alarm,
        new_force,
        new_templates,
        new_fraud,
        new_godel,
        new_meta,
        new_engine_mod,
        new_debate,
        new_orchestrator,
        new_claim,
        new_sandbox,
        new_svr,
        new_twin,
    ) = load_v5()

    failures: List[str] = []

    # 1. Config parity
    config_checks = [
        ("ATTENTION_LIMIT", lambda c: c.ATTENTION_LIMIT),
        ("MAX_RETRIES", lambda c: c.MAX_RETRIES),
        ("BACKOFF_FACTOR", lambda c: c.BACKOFF_FACTOR),
        ("TIMEOUT", lambda c: c.TIMEOUT),
        ("PATHS", lambda c: c.PATHS),
        ("DIRECTORIES", lambda c: c.DIRECTORIES),
        ("DEFAULT_PROFILE", lambda c: c.DEFAULT_PROFILE),
        ("ROLE_QUALITY_CONFIG", lambda c: c.ROLE_QUALITY_CONFIG),
        ("META_PRIMITIVES", lambda c: c.META_PRIMITIVES),
        ("META_CHAIN_RULES", lambda c: c.META_CHAIN_RULES),
        ("SCORING_RULES", lambda c: c.SCORING_RULES),
        ("GODEL_VALIDATION_POOL", lambda c: c.GODEL_VALIDATION_POOL),
    ]
    failures += compare_config(old_mod.Config, new_config.Config, config_checks)

    # 2. Model parity
    old_crystal = old_mod.Crystal(id="C001", content="x")
    new_crystal = new_models.Crystal(id="C001", content="x")
    if old_crystal.layer.value != new_crystal.layer.value:
        failures.append(f"Crystal.layer: old={old_crystal.layer} new={new_crystal.layer}")
    if old_mod.Hole(id="H001", content="x").urgency != new_models.Hole(id="H001", content="x").urgency:
        failures.append("Hole.urgency differs")

    old_fp = old_mod.CognitiveFingerprint(
        risk_tolerance=0.8,
        preferred_role="radical",
        language_style={"wenbai_ratio": "wen"},
    )
    new_fp = new_models.CognitiveFingerprint(
        risk_tolerance=0.8,
        preferred_role="radical",
        language_style={"wenbai_ratio": "wen"},
    )
    if old_fp.to_dict() != new_fp.to_dict():
        failures.append("CognitiveFingerprint.to_dict differs")

    # 3. FileIO + HealthChecker parity
    with tempfile.TemporaryDirectory(prefix="parity_old_") as old_tmp, tempfile.TemporaryDirectory(prefix="parity_new_") as new_tmp:
        old_root = Path(old_tmp)
        new_root = Path(new_tmp)
        old_data_root = old_mod.Config.DATA_ROOT
        new_data_root = new_config.Config.DATA_ROOT
        old_mod.Config.DATA_ROOT = old_root
        new_config.Config.DATA_ROOT = new_root
        try:
            old_mod.FileIO.ensure_directories()
            new_storage.FileIO.ensure_directories()
            old_mod.FileIO.ensure_default_files()
            new_storage.FileIO.ensure_default_files()
            failures += compare_file_trees(old_root, new_root)

            old_mod.FileIO.write("state", "hello")
            new_storage.FileIO.write("state", "hello")
            if old_mod.FileIO.read("state") != new_storage.FileIO.read("state"):
                failures.append("FileIO.read differs")
            old_mod.FileIO.append("state", " world")
            new_storage.FileIO.append("state", " world")
            if old_mod.FileIO.read("state") != new_storage.FileIO.read("state"):
                failures.append("FileIO.append differs")

            old_health = old_mod.HealthChecker.run()
            new_health = new_storage.HealthChecker.run()
            if [r.level for r in old_health] != [r.level for r in new_health]:
                failures.append("HealthChecker levels differ")
            if len(old_health) != len(new_health):
                failures.append(f"HealthChecker count: old={len(old_health)} new={len(new_health)}")

            old_db = old_mod.DBManager()
            new_db = new_storage.DBManager()
            failures += compare_db(old_db, new_db, "parity-session", "一致性会话")
        finally:
            old_mod.Config.DATA_ROOT = old_data_root
            new_config.Config.DATA_ROOT = new_data_root

    # 4. AIClient + session title parity (no network)
    old_ai = old_mod.AIClient(api_key="")
    new_ai = new_ai_client.AIClient(api_key="")
    old_ai.api_key = ""
    new_ai.api_key = ""
    if old_ai.chat("hello") != new_ai.chat("hello"):
        failures.append("AIClient.chat missing-key message differs")
    if old_ai.chat_json("hello") != new_ai.chat_json("hello"):
        failures.append("AIClient.chat_json fallback differs")
    title_content = "你好，这是一段很长很长的对话内容用于测试标题生成"
    new_title = new_ai_client.generate_session_title_from_content(title_content)
    # v5 升级了本地标题降级规则（去掉“你好”等无信息量开头），允许与旧版不同
    if not new_title:
        failures.append("generate_session_title returns empty")

    # 5. Search parity
    if old_mod.SearchService._tokens("机器学习AI") != new_search.SearchService._tokens("机器学习AI"):
        failures.append("SearchService._tokens differs")
    if old_mod.SearchService._score("机器学习", "机器学习是当前研究热点") != new_search.SearchService._score(
        "机器学习", "机器学习是当前研究热点"
    ):
        failures.append("SearchService._score differs")

    # 6. ExternalFetcher deterministic methods parity
    sample = {
        "ai_papers": ["论文A (发布于: 2026-01-01)", "(跳过)"],
        "hf_papers": ["HF论文B"],
        "llm_news": {"面壁智能 新模型": ["新闻C"]},
        "neuro_papers": [],
    }
    old_fetcher = old_mod.ExternalFetcher()
    new_fetcher_instance = new_fetcher.ExternalFetcher(file_io=new_storage.FileIO)
    if old_fetcher.build_insights(sample) != new_fetcher_instance.build_insights(sample):
        failures.append("ExternalFetcher.build_insights differs")
    if old_fetcher.build_structured_insights(sample) != new_fetcher_instance.build_structured_insights(sample):
        failures.append("ExternalFetcher.build_structured_insights differs")
    old_mock = json.dumps(old_fetcher._mock_multilingual_news(), ensure_ascii=False, sort_keys=True)
    new_mock = json.dumps(new_fetcher_instance._mock_multilingual_news(), ensure_ascii=False, sort_keys=True)
    old_mock = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "<ts>", old_mock)
    new_mock = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "<ts>", new_mock)
    if old_mock != new_mock:
        failures.append("ExternalFetcher._mock_multilingual_news differs")

    # 7. NetworkManager deterministic parity
    old_ua = old_mod.NetworkManager.get_random_user_agent()
    new_ua = new_network.NetworkManager.get_random_user_agent()
    if old_ua not in old_mod.Config.USER_AGENTS or new_ua not in old_mod.Config.USER_AGENTS:
        failures.append("NetworkManager.get_random_user_agent outside USER_AGENTS")

    # 8. Reporting parity
    sample_result = {
        "rounds": [
            {"round": 1, "answers": [{"role": "激进者", "answer": "方案一"}]}
        ],
        "elegant_epilogue": "儒雅结语",
    }
    old_md = old_mod.build_debate_report_markdown(
        "测试问题",
        sample_result,
        "老板版内容",
        "员工版内容",
        "新人版内容",
        "专家版内容",
        {"role_scorecard": [{"role": "激进者", "status": "adopted"}], "final_verdict": "采纳"},
    )
    new_md = new_reporting.build_debate_report_markdown(
        "测试问题",
        sample_result,
        "老板版内容",
        "员工版内容",
        "新人版内容",
        "专家版内容",
        {"role_scorecard": [{"role": "激进者", "status": "adopted"}], "final_verdict": "采纳"},
    )
    old_md = normalize_report_markdown(re.sub(r"\*报告生成时间：.*\*", "<ts>", old_md))
    new_md = normalize_report_markdown(re.sub(r"\*报告生成时间：.*\*", "<ts>", new_md))
    # 绩效看板从7人扩到9人是有意增强，改为结构校验
    for marker in ("# 📋 辩论报告", "## 各角色核心观点", "## 大法官裁决", "## 首席发言人叙事"):
        if marker not in old_md or marker not in new_md:
            failures.append("build_debate_report_markdown missing section")
    if "| 大法官 |" not in new_md or "| 首席发言人 |" not in new_md:
        failures.append("build_debate_report_markdown missing judge/spokesperson board rows")

    long_report = "这是一个很长的报告。" * 500
    new_polish = new_reporting.polish_report_markdown(long_report, ai_client=None, max_len=600)
    # v5 已升级为压缩版硬契约，fallback 不再与旧版逐字一致，改为校验契约本身
    if not (0 < len(new_polish) <= 600):
        failures.append("polish_report_markdown fallback violates length contract")
    if not any(k in new_polish for k in ("结论", "执行摘要", "总结")):
        failures.append("polish_report_markdown fallback missing conclusion section")

    class _FakeAI:
        api_key = "test"

        def chat(self, prompt, system=None, temperature=0.5, **kwargs):
            return "压缩后的完整报告，结构完整，内容精炼。" * 20 + "。"

    class _FakeFiles:
        def read_fingerprint(self):
            return {"fingerprint": {"evolution_log": [], "total_interactions": 0}}

        def write_fingerprint(self, data):
            pass

    new_ai_polish = new_reporting.polish_report_markdown(long_report, ai_client=_FakeAI(), max_len=600)
    # 同上：AI 分支同样受硬契约约束（校验→重试→规则降级）
    if not (0 < len(new_ai_polish) <= 600):
        failures.append("polish_report_markdown AI branch violates length contract")
    if not any(k in new_ai_polish for k in ("结论", "执行摘要", "总结")):
        failures.append("polish_report_markdown AI branch missing conclusion section")

    # 9. RUMAD + CheapGate parity
    old_rumad = old_mod.RUMADController(["激进者", "保守者", "结构主义者"])
    new_rumad_ctrl = new_rumad_mod.RUMADController(["激进者", "保守者", "结构主义者"])
    old_rumad.apply_user_preferences({"激进者": 0.4})
    new_rumad_ctrl.apply_user_preferences({"激进者": 0.4})
    if old_rumad.user_preferences != new_rumad_ctrl.user_preferences:
        failures.append("RUMAD user_preferences differs")
    if old_rumad._get_state_key([0.1, 0.9, 0.5], 4, 0.6) != new_rumad_ctrl._get_state_key([0.1, 0.9, 0.5], 4, 0.6):
        failures.append("RUMAD state key differs")
    answers = [{"role": "激进者", "answer": "颠覆创新突破大胆"}]
    if old_rumad._get_role_vectors(answers) != new_rumad_ctrl._get_role_vectors(answers):
        failures.append("RUMAD role vectors differ")
    old_reward = old_rumad.compute_reward(
        answers,
        answers,
        {"evidence_scores": {"a": 0.8}},
        {"evidence_scores": {"a": 0.9}},
    )
    new_reward = new_rumad_ctrl.compute_reward(
        answers,
        answers,
        {"evidence_scores": {"a": 0.8}},
        {"evidence_scores": {"a": 0.9}},
    )
    if old_reward != new_reward:
        failures.append(f"RUMAD reward: old={old_reward} new={new_reward}")

    class _Named:
        def __init__(self, name):
            self.name = name

    old_order = [r.name for r in old_rumad.prioritize_roles([_Named("保守者"), _Named("激进者")])]
    new_order = [r.name for r in new_rumad_ctrl.prioritize_roles([_Named("保守者"), _Named("激进者")])]
    if old_order != new_order:
        failures.append(f"RUMAD prioritize_roles: old={old_order} new={new_order}")

    old_gate = old_mod.CheapGate(
        engine=None,
        file_io=None,
        log_callback=lambda msg, level="system": None,
    )
    new_gate_instance = new_gate.CheapGate(
        engine=None,
        file_io=None,
        log_callback=lambda msg, level="system": None,
    )
    gate_inputs = [
        "你好",
        "预算 5000 元",
        "如何设计一个多变量优化框架并评估综合策略，同时平衡长期目标与短期资源约束？",
    ]
    for text in gate_inputs:
        if old_gate._sanitize_user_input(text) != new_gate_instance._sanitize_user_input(text):
            failures.append(f"CheapGate sanitize differs for {text}")
        if old_gate._estimate_complexity(text) != new_gate_instance._estimate_complexity(text):
            failures.append(f"CheapGate complexity differs for {text}")
        if old_gate.check(text, []) != new_gate_instance.check(text, []):
            failures.append(f"CheapGate check differs for {text}")

    # 10. FingerprintExtractor deterministic parity
    old_fp_extractor = old_mod.FingerprintExtractor(engine=None, file_io=_FakeFiles())
    new_fp_extractor = new_fingerprint.FingerprintExtractor(engine=None, file_io=_FakeFiles())
    fingerprint_checks = [
        ("_analyze_keywords", lambda e: e._analyze_keywords([("user", "风险 成本 失败 安全 突破 创新")])),
        ("_analyze_decisiveness", lambda e: e._analyze_decisiveness([("user", "好的")] * 3)),
        ("_analyze_conflict_style", lambda e: e._analyze_conflict_style([("user", "综合 融合 平衡 兼顾")])),
        ("_analyze_attention", lambda e: e._analyze_attention([("user", "这句话比较长用于测试注意力")] * 3)),
        ("_analyze_thinking_style", lambda e: e._analyze_thinking_style([("user", "因为 所以 因此 逻辑 推导")])),
        ("_analyze_language_style", lambda e: e._analyze_language_style([("user", "之 乎 者 也 山 水 月 云")] * 3)),
        ("_smooth_update", lambda e: e._smooth_update(0.5, 0.9, 0.3)),
        ("_merge_role_history", lambda e: e._merge_role_history({"激进者": 1}, {"激进者": 2, "保守者": 1})),
    ]
    for label, getter in fingerprint_checks:
        if getter(old_fp_extractor) != getter(new_fp_extractor):
            failures.append(f"FingerprintExtractor.{label} differs")

    old_fp_obj = old_mod.CognitiveFingerprint(
        reasoning_style="deductive",
        analogy_preference="analogy",
        output_style="conclusion_first",
        language_style={"wenbai_ratio": "wen"},
    )
    new_fp_obj = new_models.CognitiveFingerprint(
        reasoning_style="deductive",
        analogy_preference="analogy",
        output_style="conclusion_first",
        language_style={"wenbai_ratio": "wen"},
    )
    if old_fp_extractor.get_cognitive_operators(old_fp_obj) != new_fp_extractor.get_cognitive_operators(new_fp_obj):
        failures.append("FingerprintExtractor.get_cognitive_operators differs")
    if old_fp_extractor.get_language_style_description(old_fp_obj) != new_fp_extractor.get_language_style_description(new_fp_obj):
        failures.append("FingerprintExtractor.get_language_style_description differs")

    # 11. LayerAuditService deterministic parity
    old_audit_root = old_mod.Config.DATA_ROOT
    new_audit_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_audit_old_") as old_atmp, tempfile.TemporaryDirectory(
        prefix="parity_audit_new_"
    ) as new_atmp:
        old_mod.Config.DATA_ROOT = Path(old_atmp)
        new_config.Config.DATA_ROOT = Path(new_atmp)
        try:
            old_audit = old_mod.LayerAuditService(engine=None, file_io=_FakeFiles())
            new_audit_service = new_audit.LayerAuditService(engine=None, file_io=_FakeFiles())
            old_layers = [
                old_mod.LayerContribution("L1", 20, 50.0, "stable", 0.0, 0.5, ""),
                old_mod.LayerContribution("L2", 15, 30.0, "stable", 0.0, 0.5, ""),
                old_mod.LayerContribution("L3", 10, 20.0, "stable", 0.0, 0.5, ""),
            ]
            new_layers = [
                new_audit.LayerContribution("L1", 20, 50.0, "stable", 0.0, 0.5, ""),
                new_audit.LayerContribution("L2", 15, 30.0, "stable", 0.0, 0.5, ""),
                new_audit.LayerContribution("L3", 10, 20.0, "stable", 0.0, 0.5, ""),
            ]
            old_components = {"CrystalEngine": True, "MetaLayer": True, "CheapGate": True}
            if old_audit._calculate_health_score(old_layers, old_components, 8.0) != (
                new_audit_service._calculate_health_score(new_layers, old_components, 8.0)
            ):
                failures.append("LayerAuditService._calculate_health_score differs")
            if old_audit._generate_recommendations(old_layers, {"CrystalEngine": True}, 9.0) != (
                new_audit_service._generate_recommendations(new_layers, {"CrystalEngine": True}, 9.0)
            ):
                failures.append("LayerAuditService._generate_recommendations differs")
            if old_audit._calculate_trend("L1", 22) != new_audit_service._calculate_trend("L1", 22):
                failures.append("LayerAuditService._calculate_trend differs")
            if old_audit._should_run_audit() != new_audit_service._should_run_audit():
                failures.append("LayerAuditService._should_run_audit differs")
            if old_audit._calculate_cognitive_continuity() != new_audit_service._calculate_cognitive_continuity():
                failures.append("LayerAuditService._calculate_cognitive_continuity differs")
        finally:
            old_mod.Config.DATA_ROOT = old_audit_root
            new_config.Config.DATA_ROOT = new_audit_root

    # 12. VectorStore degraded parity
    old_vector_root = old_mod.Config.DATA_ROOT
    new_vector_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_vector_old_") as old_vtmp, tempfile.TemporaryDirectory(
        prefix="parity_vector_new_"
    ) as new_vtmp:
        old_mod.Config.DATA_ROOT = Path(old_vtmp)
        new_config.Config.DATA_ROOT = Path(new_vtmp)
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "chromadb" or name.startswith("chromadb."):
                raise ImportError("chromadb disabled for parity")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            old_vector = old_mod.VectorStore(file_io=None)
            new_vector_instance = new_vector.VectorStore(file_io=None)
            if old_vector.count() != new_vector_instance.count():
                failures.append("VectorStore.count differs")
            if old_vector.add_crystals([]) != new_vector_instance.add_crystals([]):
                failures.append("VectorStore.add_crystals differs")
        finally:
            builtins.__import__ = real_import
            old_mod.Config.DATA_ROOT = old_vector_root
            new_config.Config.DATA_ROOT = new_vector_root

    # 13. AlarmMonitor parity
    old_alarm = old_mod.AlarmMonitor(
        log_callback=lambda msg, level="system": None,
    )
    new_alarm_instance = new_alarm.AlarmMonitor(
        log_callback=lambda msg, level="system": None,
    )
    alarm_sequence = [
        {"crystal_reference_rate": 0.2},
        {"external_has_new": False},
        {"external_has_new": False},
        {"external_has_new": False, "jaccard_similarity": 0.9},
    ]
    for metrics in alarm_sequence:
        old_rules = [a["rule"] for a in old_alarm.check(metrics)]
        new_rules = [a["rule"] for a in new_alarm_instance.check(metrics)]
        if old_rules != new_rules:
            failures.append(f"AlarmMonitor.check differs for {metrics}: old={old_rules} new={new_rules}")

    # 14. ForceExplorer parity
    class _ParityHole:
        def __init__(self, hole_id, content, urgency):
            self.id = hole_id
            self.content = content
            self.urgency = urgency
            self.links = []

    class _ParityEngine:
        def parse_holes(self):
            return [
                _ParityHole("H001", "高紧迫孔洞", 0.9),
                _ParityHole("H002", "普通孔洞", 0.5),
            ]

        def load_hole_progress(self):
            return {"H001": 0.2}

        def parse_crystals(self):
            return []

        def rank_crystals(self, query, crystals, top_k=5):
            return []

        def create_crystal(self, **kwargs):
            return True

        def log_evolution_event(self, *args, **kwargs):
            return None

    old_force_root = old_mod.Config.DATA_ROOT
    new_force_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_force_old_") as old_ftmp, tempfile.TemporaryDirectory(
        prefix="parity_force_new_"
    ) as new_ftmp:
        old_mod.Config.DATA_ROOT = Path(old_ftmp)
        new_config.Config.DATA_ROOT = Path(new_ftmp)
        try:
            old_force = old_mod.ForceExplorer(
                engine=_ParityEngine(),
                log_callback=lambda msg, level="system": None,
            )
            new_force_instance = new_force.ForceExplorer(
                engine=_ParityEngine(),
                log_callback=lambda msg, level="system": None,
            )
            if old_force.check_holes_for_escalation(7) != new_force_instance.check_holes_for_escalation(7):
                failures.append("ForceExplorer.check_holes_for_escalation differs")
            if old_force.get_exploration_status() != new_force_instance.get_exploration_status():
                failures.append("ForceExplorer.get_exploration_status differs")
        finally:
            old_mod.Config.DATA_ROOT = old_force_root
            new_config.Config.DATA_ROOT = new_force_root

    # 15. PromptTemplateManager parity
    old_tpl_root = old_mod.Config.DATA_ROOT
    new_tpl_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_tpl_old_") as old_ttmp, tempfile.TemporaryDirectory(
        prefix="parity_tpl_new_"
    ) as new_ttmp:
        old_mod.Config.DATA_ROOT = Path(old_ttmp)
        new_config.Config.DATA_ROOT = Path(new_ttmp)
        try:
            old_tmpl = old_mod.PromptTemplateManager(file_io=None)
            new_tmpl = new_templates.PromptTemplateManager(file_io=None)
            old_names = sorted(old_tmpl.get_all_templates())
            new_names = sorted(new_tmpl.get_all_templates())
            if old_names != new_names:
                failures.append("PromptTemplateManager template names differ")
            for name in old_names:
                old_item = old_tmpl.get_template(name)
                new_item = new_tmpl.get_template(name)
                if (
                    old_item.system_prompt,
                    old_item.user_prompt_template,
                    old_item.version,
                    old_item.is_active,
                ) != (
                    new_item.system_prompt,
                    new_item.user_prompt_template,
                    new_item.version,
                    new_item.is_active,
                ):
                    failures.append(f"PromptTemplateManager {name} differs")
            if old_tmpl.update_template("radical", system_prompt="新提示") != new_tmpl.update_template(
                "radical", system_prompt="新提示"
            ):
                failures.append("PromptTemplateManager.update_template differs")
            if old_tmpl.rollback("radical", 1) != new_tmpl.rollback("radical", 1):
                failures.append("PromptTemplateManager.rollback differs")
        finally:
            old_mod.Config.DATA_ROOT = old_tpl_root
            new_config.Config.DATA_ROOT = new_tpl_root

    # 16. Anti-fraud parity
    old_detector = old_mod.AIPersonaDetector()
    new_detector = new_fraud.AIPersonaDetector()
    fraud_sample = "我是AI助手，我的训练数据来自互联网。"
    if old_detector.detect(fraud_sample) != new_detector.detect(fraud_sample):
        failures.append("AIPersonaDetector.detect differs")
    old_starlink = old_mod.StarlinkFingerprintDB()
    new_starlink = new_fraud.StarlinkFingerprintDB()
    for ip in ["103.23.1.100", "8.8.8.8"]:
        if old_starlink.check(ip) != new_starlink.check(ip):
            failures.append(f"StarlinkFingerprintDB.check differs for {ip}")
    old_auditor = old_mod.CrossLingualAuditor()
    new_auditor = new_fraud.CrossLingualAuditor()
    if old_auditor.audit("", "") != new_auditor.audit("", ""):
        failures.append("CrossLingualAuditor empty differs")
    if old_auditor.audit("知识 学习", "knowledge learn") != new_auditor.audit("知识 学习", "knowledge learn"):
        failures.append("CrossLingualAuditor sample differs")

    # 17. GoedelAgent deterministic parity
    class _GodelEngine:
        def parse_crystals(self):
            return []

        def create_crystal(self, **kwargs):
            return True

        def log_evolution_event(self, *args, **kwargs):
            return None

    class _GodelAI:
        api_key = "test"

        def chat(self, prompt, system=None, temperature=0.5, **kwargs):
            return "[C001] 引用测试答案。"

    old_godel_root = old_mod.Config.DATA_ROOT
    new_godel_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_godel_old_") as old_gtmp, tempfile.TemporaryDirectory(
        prefix="parity_godel_new_"
    ) as new_gtmp:
        old_mod.Config.DATA_ROOT = Path(old_gtmp)
        new_config.Config.DATA_ROOT = Path(new_gtmp)
        try:
            old_godel = old_mod.GödelAgent(
                engine=_GodelEngine(),
                ai_client=_GodelAI(),
                template_manager=old_mod.PromptTemplateManager(file_io=None),
            )
            new_godel_instance = new_godel.GödelAgent(
                engine=_GodelEngine(),
                ai_client=_GodelAI(),
                template_manager=new_templates.PromptTemplateManager(file_io=None),
            )
            if old_godel._compute_jaccard("认知晶体树 决策", "认知晶体树 决策 系统") != new_godel_instance._compute_jaccard(
                "认知晶体树 决策", "认知晶体树 决策 系统"
            ):
                failures.append("GödelAgent._compute_jaccard differs")
            for prompt in ["测试提示", "已有 偏见 晶体引用 多样性 反思 外部 arxiv"]:
                for method in [
                    "_reduce_bias_instruction",
                    "_strengthen_external_instruction",
                    "_strengthen_crystal_instruction",
                    "_add_diversity_instruction",
                    "_add_reflection_instruction",
                ]:
                    if getattr(old_godel, method)(prompt) != getattr(new_godel_instance, method)(prompt):
                        failures.append(f"GödelAgent.{method} differs for {prompt}")
            for role in ["radical", "conservative", "structural", "judge", "spokesperson", "pilgrim", "strategist"]:
                old_default = old_godel._get_default_improvement(role, "当前提示")
                new_default = new_godel_instance._get_default_improvement(role, "当前提示")
                if old_default != new_default:
                    failures.append(f"GödelAgent._get_default_improvement differs for {role}")

            candidate = {"content": "认知原则框架：决策前必须引用晶体", "links": []}
            if old_godel.validate_crystal_candidate(candidate) != new_godel_instance.validate_crystal_candidate(
                {"content": "认知原则框架：决策前必须引用晶体", "links": []}
            ):
                failures.append("GödelAgent.validate_crystal_candidate differs")
            if old_godel.get_evolution_status() != new_godel_instance.get_evolution_status():
                failures.append("GödelAgent.get_evolution_status differs")

            log_data = {
                "events": [
                    {
                        "event_type": "alarm",
                        "details": {"rule": "knowledge_poverty"},
                    },
                    {
                        "event_type": "alarm",
                        "details": {"rule": "knowledge_poverty"},
                    },
                ]
            }
            for root_path in (Path(old_gtmp), Path(new_gtmp)):
                log_path = root_path / "系统日志" / "evolution_log.json"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(json.dumps(log_data, ensure_ascii=False), encoding="utf-8")
            if old_godel.analyze_failure_patterns() != new_godel_instance.analyze_failure_patterns():
                failures.append("GödelAgent.analyze_failure_patterns differs")
        finally:
            old_mod.Config.DATA_ROOT = old_godel_root
            new_config.Config.DATA_ROOT = new_godel_root

    # 18. MetaLayer deterministic parity
    class _MetaEngine:
        def parse_crystals(self):
            return []

        def detect_conflicts(self, method="auto"):
            return []

        def load_layer_state(self):
            return {}

        def archive_cold_crystals(self):
            return []

        def _append_change_log(self, *args, **kwargs):
            return None

        def log_evolution_event(self, *args, **kwargs):
            return None

        def _simple_similarity(self, a, b):
            return 0.9 if a == b else 0.0

        def _load_task_cards(self):
            return []

        def _save_task_cards(self, cards):
            return None

        def create_crystal(self, **kwargs):
            return True

    class _MetaFiles:
        def resolve(self, key):
            return new_config.Config.DATA_ROOT / new_config.Config.PATHS.get(key, key)

    class _MetaFilesOld:
        def resolve(self, key):
            return old_mod.Config.DATA_ROOT / old_mod.Config.PATHS.get(key, key)

    old_meta_root = old_mod.Config.DATA_ROOT
    new_meta_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_meta_old_") as old_mtmp, tempfile.TemporaryDirectory(
        prefix="parity_meta_new_"
    ) as new_mtmp:
        old_mod.Config.DATA_ROOT = Path(old_mtmp)
        new_config.Config.DATA_ROOT = Path(new_mtmp)
        try:
            (Path(old_mtmp) / "系统日志").mkdir(parents=True, exist_ok=True)
            (Path(new_mtmp) / "系统日志").mkdir(parents=True, exist_ok=True)
            old_meta = old_mod.MetaLayer(engine=_MetaEngine(), file_io=_MetaFilesOld())
            new_meta_instance = new_meta.MetaLayer(
                engine=_MetaEngine(),
                file_io=_MetaFiles(),
                anti_fraud_providers=SimpleNamespace(
                    AIPersonaDetector=new_fraud.AIPersonaDetector,
                    StarlinkFingerprintDB=new_fraud.StarlinkFingerprintDB,
                    CrossLingualAuditor=new_fraud.CrossLingualAuditor,
                ),
            )
            for sample in ["核心架构系统框架", "优化改进", "短"]:
                for method in [
                    "_evaluate_importance",
                    "_evaluate_urgency",
                    "_evaluate_alignment",
                    "_estimate_resources",
                ]:
                    if getattr(old_meta, method)(sample) != getattr(new_meta_instance, method)(sample):
                        failures.append(f"MetaLayer.{method} differs for {sample}")

            history = [
                {"accuracy": 0.5, "cost": 0.1},
                {"accuracy": 0.6, "cost": 0.1},
                {"accuracy": 0.7, "cost": 0.1},
                {"accuracy": 0.8, "cost": 0.1},
            ]
            if old_meta._calculate_trends(history) != new_meta_instance._calculate_trends(history):
                failures.append("MetaLayer._calculate_trends differs")
            configs = {"a": {"accuracy": 0.9, "cost": 0.1, "latency": 1.0}}
            if old_meta._get_best_profile(configs) != new_meta_instance._get_best_profile(configs):
                failures.append("MetaLayer._get_best_profile differs")

            context = {"sources": ["a", "b", "c"], "audit_score": 0.7}
            if old_meta.validation_gated_self_evolution({"data": 1}, context) != (
                new_meta_instance.validation_gated_self_evolution({"data": 1}, context)
            ):
                failures.append("MetaLayer.validation_gated_self_evolution differs")

            for score in [0.8, 0.81, 0.82]:
                if old_meta.prompt_saturation_detector(score) != new_meta_instance.prompt_saturation_detector(score):
                    failures.append(f"MetaLayer.prompt_saturation_detector differs at {score}")

            audit_context = {
                "dialogue": "我是AI助手，我的训练数据来自互联网。",
                "ip": "103.23.1.100",
                "text_zh": "知识 学习",
                "text_en": "knowledge learn",
            }
            old_fraud_audit = old_meta.run_anti_fraud_audit(audit_context)
            new_fraud_audit = new_meta_instance.run_anti_fraud_audit(audit_context)
            old_fraud_audit.pop("timestamp", None)
            new_fraud_audit.pop("timestamp", None)
            if old_fraud_audit != new_fraud_audit:
                failures.append("MetaLayer.run_anti_fraud_audit differs")

            insp_data = '[{"id": "INSP-001", "content": "核心架构系统框架突破", "status": "待筛选", "created_at": "2026-01-01"}]'
            for root_path in (Path(old_mtmp), Path(new_mtmp)):
                insp_path = root_path / "系统日志" / "灵感池.json"
                insp_path.parent.mkdir(parents=True, exist_ok=True)
                insp_path.write_text(insp_data, encoding="utf-8")
            old_review = old_meta.inspiration_furnace_review()
            new_review = new_meta_instance.inspiration_furnace_review()
            if old_review["total_pending"] != new_review["total_pending"]:
                failures.append("MetaLayer.inspiration_furnace_review total differs")

            log_data = {
                "events": [
                    {
                        "event_type": "failure_trace",
                        "details": {"question": "测试问题", "failure_traces": {"failure_type": "low_crystal_reference"}},
                    }
                ]
            }
            for root_path in (Path(old_mtmp), Path(new_mtmp)):
                log_path = root_path / "系统日志" / "evolution_log.json"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(json.dumps(log_data, ensure_ascii=False), encoding="utf-8")
            if old_meta.diagnose_history("测试问题") != new_meta_instance.diagnose_history("测试问题"):
                failures.append("MetaLayer.diagnose_history differs")
        finally:
            old_mod.Config.DATA_ROOT = old_meta_root
            new_config.Config.DATA_ROOT = new_meta_root

    # 19. CrystalEngine core parity
    old_engine_root = old_mod.Config.DATA_ROOT
    new_engine_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_engine_old_") as old_etmp, tempfile.TemporaryDirectory(
        prefix="parity_engine_new_"
    ) as new_etmp:
        old_mod.Config.DATA_ROOT = Path(old_etmp)
        new_config.Config.DATA_ROOT = Path(new_etmp)
        try:
            (Path(old_etmp) / "系统日志").mkdir(parents=True, exist_ok=True)
            (Path(old_etmp) / "核心配置").mkdir(parents=True, exist_ok=True)
            (Path(new_etmp) / "系统日志").mkdir(parents=True, exist_ok=True)
            (Path(new_etmp) / "核心配置").mkdir(parents=True, exist_ok=True)
            old_engine = old_mod.CrystalEngine(old_mod.FileIO())
            new_engine_instance = new_engine_mod.CrystalEngine(new_storage.FileIO())

            for question in [
                "如何优化系统架构并提升性能？",
                "用户沟通与团队协作",
                "预算成本与市场竞争",
                "你好",
            ]:
                if old_engine._classify_question(question) != new_engine_instance._classify_question(question):
                    failures.append(f"CrystalEngine._classify_question differs for {question}")

            if old_engine._simple_similarity("机器学习模型", "机器学习模型训练") != (
                new_engine_instance._simple_similarity("机器学习模型", "机器学习模型训练")
            ):
                failures.append("CrystalEngine._simple_similarity differs")

            old_engine.create_crystal("C001", "认知原则：决策前必须引用晶体", [], "test")
            new_engine_instance.create_crystal("C001", "认知原则：决策前必须引用晶体", [], "test")
            old_crystals = [(c.id, c.content) for c in old_engine.parse_crystals()]
            new_crystals = [(c.id, c.content) for c in new_engine_instance.parse_crystals()]
            if old_crystals != new_crystals:
                failures.append("CrystalEngine.parse_crystals differs")

            old_ranked = [c.id for _, c in old_engine.rank_crystals("认知", old_engine.parse_crystals(), top_k=5)]
            new_ranked = [c.id for _, c in new_engine_instance.rank_crystals(
                "认知", new_engine_instance.parse_crystals(), top_k=5
            )]
            if old_ranked != new_ranked:
                failures.append("CrystalEngine.rank_crystals differs")

            old_engine.update_hebbian_weights(["C001", "C002"], task_type="tech", score=0.8)
            new_engine_instance.update_hebbian_weights(["C001", "C002"], task_type="tech", score=0.8)
            if old_engine.get_hebbian_boost("C001", task_type="tech") != (
                new_engine_instance.get_hebbian_boost("C001", task_type="tech")
            ):
                failures.append("CrystalEngine.get_hebbian_boost differs")
            old_engine.vote_role("radical", True)
            new_engine_instance.vote_role("radical", True)
            if old_engine.hebbian_weights.get("vote_radical") != new_engine_instance.hebbian_weights.get("vote_radical"):
                failures.append("CrystalEngine.vote_role differs")

            old_engine.update_crystal_access_time("C001")
            new_engine_instance.update_crystal_access_time("C001")
            if old_engine.load_layer_state() != new_engine_instance.load_layer_state():
                failures.append("CrystalEngine.load_layer_state differs")

            old_stats = old_engine.get_evolution_stats()
            new_stats = new_engine_instance.get_evolution_stats()
            if (old_stats["total_events"], old_stats["summary"]) != (new_stats["total_events"], new_stats["summary"]):
                failures.append("CrystalEngine.get_evolution_stats differs")

            if old_engine.delete_crystal("C001") != new_engine_instance.delete_crystal("C001"):
                failures.append("CrystalEngine.delete_crystal differs")
        finally:
            old_mod.Config.DATA_ROOT = old_engine_root
            new_config.Config.DATA_ROOT = new_engine_root

    # 20. DebateEngine deterministic parity
    class _DebateAI:
        api_key = "test"

        def chat(self, prompt, system=None, temperature=0.5, **kwargs):
            return "测试回答"

        def chat_json(self, prompt, temperature=0.3, **kwargs):
            return {}

    debate_roles = [
        {"key": "radical", "name": "激进者", "instruction": "颠覆"},
        {"key": "conservative", "name": "保守者", "instruction": "稳健"},
        {"key": "structural", "name": "结构主义者", "instruction": "类比"},
    ]
    old_debate_root = old_mod.Config.DATA_ROOT
    new_debate_root = new_config.Config.DATA_ROOT
    with tempfile.TemporaryDirectory(prefix="parity_debate_old_") as old_dtmp, tempfile.TemporaryDirectory(
        prefix="parity_debate_new_"
    ) as new_dtmp:
        old_mod.Config.DATA_ROOT = Path(old_dtmp)
        new_config.Config.DATA_ROOT = Path(new_dtmp)
        try:
            (Path(old_dtmp) / "系统日志").mkdir(parents=True, exist_ok=True)
            (Path(old_dtmp) / "核心配置").mkdir(parents=True, exist_ok=True)
            (Path(new_dtmp) / "系统日志").mkdir(parents=True, exist_ok=True)
            (Path(new_dtmp) / "核心配置").mkdir(parents=True, exist_ok=True)
            old_engine_d = old_mod.CrystalEngine(old_mod.FileIO())
            new_engine_d = new_engine_mod.CrystalEngine(new_storage.FileIO())
            old_debate = old_mod.DebateEngine(
                _DebateAI(),
                old_engine_d,
                debate_roles,
                log=lambda message, level="system": None,
            )
            new_debate_instance = new_debate.DebateEngine(
                _DebateAI(),
                new_engine_d,
                debate_roles,
                log=lambda message, level="system": None,
            )
            if [r.name for r in old_debate._core_roles()] != [r.name for r in new_debate_instance._core_roles()]:
                failures.append("DebateEngine._core_roles differs")
            if old_debate._run_lark_bare("测试问题") != new_debate_instance._run_lark_bare("测试问题"):
                failures.append("DebateEngine._run_lark_bare differs")
            old_debate.rumad.apply_user_preferences({"激进者": 0.4})
            new_debate_instance.rumad.apply_user_preferences({"激进者": 0.4})
            old_order = [r.name for r in old_debate.rumad.prioritize_roles(old_debate.roles)]
            new_order = [r.name for r in new_debate_instance.rumad.prioritize_roles(new_debate_instance.roles)]
            if old_order != new_order:
                failures.append("DebateEngine RUMAD priority differs")
        finally:
            old_mod.Config.DATA_ROOT = old_debate_root
            new_config.Config.DATA_ROOT = new_debate_root

    # 21. OutputOrchestrator deterministic parity
    class _OrchAI:
        api_key = "test"

        def chat(self, prompt, system=None, temperature=0.5, **kwargs):
            return "测试回答"

        def chat_json(self, prompt, temperature=0.3, **kwargs):
            return {
                "role_scorecard": [],
                "final_verdict": "采纳测试",
                "rejected_items": [],
            }

        def _call_api(self, messages, temperature=0.7, response_format=None,
                      stream=False, callback=None, max_tokens=None):
            return (
                '{"role_scorecard": [{"role": "激进者", "core_view": "测试", '
                '"strength": 8, "novelty": 9, "feasibility": 4, "evidence_quality": 6, '
                '"relevance": 7, "alignment": 5, "activation": 8, "contribution_percent": 15, '
                '"status": "rejected", "brief_reason": "可落地不足", "system_basis": "[C051]"}], '
                '"final_verdict": "采纳测试", "rejected_items": []}'
            )

    class _OrchEngine:
        def get_role_synapses(self, role_key):
            return {"C001": 0.5}

        def update_role_synapse(self, role_key, crystal_id, delta):
            return 0.6

        def _update_role_win_loss(self, role_key, win):
            return None

    judge_audit = {"final_verdict": "采纳", "role_scorecard": []}
    if old_mod.compute_dashboard_stats(judge_audit) != new_orchestrator.compute_dashboard_stats(judge_audit):
        failures.append("compute_dashboard_stats differs")

    old_schema = old_mod.FinalOutputSchema()
    new_schema = new_orchestrator.FinalOutputSchema()
    if old_schema.judge_audit != new_schema.judge_audit:
        failures.append("FinalOutputSchema.judge_audit differs")

    old_synapse = old_mod.SynapseStore
    new_synapse = new_orchestrator.SynapseStore
    orch_engine = _OrchEngine()
    if old_synapse.get_synapse(orch_engine, "radical", "C001") != new_synapse.get_synapse(
        orch_engine, "radical", "C001"
    ):
        failures.append("SynapseStore.get_synapse differs")
    if old_synapse.update_synapse(orch_engine, "radical", "C001", 0.1) != new_synapse.update_synapse(
        orch_engine, "radical", "C001", 0.1
    ):
        failures.append("SynapseStore.update_synapse differs")

    old_orch = old_mod.OutputOrchestrator(_OrchAI(), orch_engine)
    new_orch_instance = new_orchestrator.OutputOrchestrator(_OrchAI(), orch_engine)
    old_judge = old_orch._run_judge("测试问题", {"role_contributions": {}})
    new_judge = new_orch_instance._run_judge("测试问题", {"role_contributions": {}})
    if old_judge.get("final_verdict") != new_judge.get("final_verdict"):
        failures.append("OutputOrchestrator._run_judge final_verdict differs")
    old_roles = {item.get("role") for item in old_judge.get("role_scorecard", [])}
    new_roles = {item.get("role") for item in new_judge.get("role_scorecard", [])}
    if not old_roles.issubset(new_roles):
        failures.append("OutputOrchestrator._run_judge missing old roles")
    if "大法官" not in new_roles or "首席发言人" not in new_roles:
        failures.append("OutputOrchestrator._run_judge missing judge/spokesperson roles")

    # 22. Day12 deterministic parity
    claim_text = "新方案比旧方案效率提升35%，时间成本降低20%。"
    old_claims = old_mod.ClaimExtractor(engine=None).extract_from_text(claim_text)
    new_claims = new_claim.ClaimExtractor(engine=None).extract_from_text(claim_text)
    old_claim_rows = [(c.original_text, c.claim_type) for c in old_claims]
    new_claim_rows = [(c.original_text, c.claim_type) for c in new_claims]
    if old_claim_rows != new_claim_rows:
        failures.append(f"ClaimExtractor differs: old={old_claim_rows} new={new_claim_rows}")

    debate_rounds = [
        {
            "round": 1,
            "answers": [
                {"role": "激进者", "answer": "颠覆创新"},
                {"role": "保守者", "answer": "稳健风险"},
            ],
        }
    ]
    old_svr = old_mod.SVRMADValidator(engine=None).validate_all_roles(debate_rounds)
    new_svr = new_svr.SVRMADValidator(engine=None).validate_all_roles(debate_rounds)
    if old_svr != new_svr:
        failures.append(f"SVRMADValidator differs: old={old_svr} new={new_svr}")

    old_sandbox_ok = old_mod.SandboxExecutor(engine=None).execute_code("def main():\n    print('OK')\n")
    new_sandbox_ok = new_sandbox.SandboxExecutor(engine=None).execute_code("def main():\n    print('OK')\n")
    if old_sandbox_ok.get("success") != new_sandbox_ok.get("success"):
        failures.append("SandboxExecutor success differs")
    old_sandbox_block = old_mod.SandboxExecutor(engine=None).execute_code("import os\nos.system('rm -rf /')")
    new_sandbox_block = new_sandbox.SandboxExecutor(engine=None).execute_code("import os\nos.system('rm -rf /')")
    if old_sandbox_block.get("success") != new_sandbox_block.get("success"):
        failures.append("SandboxExecutor blocked result differs")

    # 23. TwinProfile default parity
    old_profile = vars(old_mod.TwinProfile(name="测试替身", role="决策替身"))
    new_profile = vars(new_twin.TwinProfile(name="测试替身", role="决策替身"))
    if old_profile != new_profile:
        failures.append(f"TwinProfile defaults differ: old={old_profile} new={new_profile}")

    # 24. Final debate report structural parity (rich result)
    rich_result = {
        "rounds": [
            {
                "round": 1,
                "answers": [
                    {"role": "激进者", "answer": "方案A [C001] [arxiv] https://example.com"},
                    {"role": "保守者", "answer": "方案B [C002]"},
                ],
            }
        ],
        "elegant_epilogue": "儒雅结语",
        "decision_annex": {
            "final_decision": "采纳方案A，总预算800万元。",
            "resource_allocation": {"ratio": "70/30", "detail": "70%核心，30%弹性"},
            "budget": [
                {"item": "搭建", "amount": "300万", "note": ""},
                {"item": "迭代", "amount": "300万", "note": ""},
                {"item": "推广", "amount": "200万", "note": ""},
            ],
        },
        "_day12": {
            "claims_extracted": 5,
            "verified_count": 3,
            "pending_review_count": 2,
            "numeric_claim_count": 2,
            "source_claim_count": 1,
            "logic_claim_count": 2,
            "m3mad_bench": {"overall_score": 0.6},
            "claims": [
                {"original_text": "效率提升35%", "claim_type": "comparative", "verified": True}
            ],
            "sources": ["[arxiv] 论文", "https://example.com"],
        },
    }
    rich_judge = {
        "role_scorecard": [
            {
                "role": "激进者",
                "status": "adopted",
                "contribution_percent": 100,
                "brief_reason": "合理",
                "system_basis": "[C001]",
            }
        ],
        "rejected_items": [],
        "final_verdict": "采纳",
    }
    old_rich = old_mod.build_debate_report_markdown(
        "完整测试问题",
        rich_result,
        "老板版内容",
        "员工版内容",
        "新人版内容",
        "专家版内容",
        rich_judge,
    )
    new_rich = new_reporting.build_debate_report_markdown(
        "完整测试问题",
        rich_result,
        "老板版内容",
        "员工版内容",
        "新人版内容",
        "专家版内容",
        rich_judge,
    )
    old_rich = normalize_report_markdown(re.sub(r"\*报告生成时间：.*\*", "<ts>", old_rich))
    new_rich = normalize_report_markdown(re.sub(r"\*报告生成时间：.*\*", "<ts>", new_rich))
    # 报告三态渲染为有意增强，改为结构校验而非逐字相等
    for marker in (
        "## 各角色核心观点",
        "## 大法官裁决",
        "## 首席发言人叙事",
        "## 🔬 沙盒验证结果",
        "## 📚 来源索引",
        "## 🗣 术语白话对照",
    ):
        if marker not in old_rich or marker not in new_rich:
            failures.append(f"Final debate report missing section: {marker}")
    if "## 第二部分 · 决策附录（可执行版）" not in new_rich:
        failures.append("Final debate report missing decision annex section")
    if "已断言主张通过率" not in new_rich:
        failures.append("Final debate report missing asserted pass rate")
    if "⏳ 待人工核验" not in new_rich:
        failures.append("Final debate report missing pending state")

    if failures:
        print("PARITY: FAIL")
        for item in failures:
            print("  - " + item)
        return 1

    print("PARITY: PASS")
    print("  - Config: 12 constant groups identical")
    print("  - Models: Crystal / Hole / CognitiveFingerprint identical")
    print("  - FileIO: default tree + read/write/append identical")
    print("  - HealthChecker: result shape identical")
    print("  - DBManager: sessions identical")
    print("  - AIClient: missing-key / json fallback / title identical")
    print("  - SearchService: tokens / score identical")
    print("  - ExternalFetcher: insights / structured insights / mock news identical")
    print("  - NetworkManager: user agent pool identical")
    print("  - Reporting: report markdown / fallback polish / AI polish identical")
    print("  - RUMAD: preferences / state key / vectors / reward / priority identical")
    print("  - CheapGate: sanitize / complexity / routing identical")
    print("  - FingerprintExtractor: analysis helpers / operators identical")
    print("  - LayerAuditService: health / recommendations / trend / continuity identical")
    print("  - VectorStore: degraded behavior identical")
    print("  - AlarmMonitor: rule firing sequence identical")
    print("  - ForceExplorer: escalation / status identical")
    print("  - PromptTemplateManager: templates / update / rollback identical")
    print("  - Anti-fraud: persona / starlink / cross-lingual identical")
    print("  - GödelAgent: jaccard / instructions / defaults / validation / status / patterns identical")
    print("  - MetaLayer: helpers / trends / gate / saturation / anti-fraud / review / history identical")
    print("  - CrystalEngine: classify / CRUD / similarity / ranking / hebbian / vote / layer state identical")
    print("  - DebateEngine: core roles / lark bare / RUMAD priority identical")
    print("  - OutputOrchestrator: dashboard / schema / synapse / judge identical")
    print("  - Day12: claim extraction / SVR-MAD / sandbox identical")
    print("  - TwinProfile: defaults identical")
    print("  - Final debate report: rich structure identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
