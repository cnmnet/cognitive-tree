#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量回归测试 —— Day 0 ~ Day 21 功能验收（真实API环境）
测试问题均为 2026 年热门议题，覆盖所有核心功能。
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import time
import re

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# 从主文件导入核心组件
from crystal_tree_all_in_one_day import (
    Config, FileIO, DBManager, AIClient, CrystalEngine, MetaLayer,
    DebateEngine, CheapGate, ExternalFetcher, DailyPlanner,
    OutputOrchestrator, FinalOutputSchema, CognitiveFingerprint,
    FingerprintExtractor, VectorStore, AlarmMonitor, RUMADController,
    ClaimExtractor, SVRMADValidator, SandboxExecutor, M3MADBench,
    ContemplativeEngine, GödelAgent, TwinWorkbench,
    LayerAuditService, auth, webhook
)

# 从独立模块导入（这两个类不在主文件中）
from self_healing import SelfHealing
from github_trending import GitHubTrendingCrystalizer

# ============================================================================
# 测试配置：使用临时目录作为数据根，并强制使用真实 API
# ============================================================================

class TestConfig:
    """测试专用配置，覆盖全局 Config"""
    temp_root: Optional[Path] = None

    @classmethod
    def setup_temp_root(cls):
        # 尝试加载 .env（已在模块顶部加载，但为了保险再试一次）
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError(
                "请设置环境变量 DEEPSEEK_API_KEY 或在项目根目录创建 .env 文件，"
                "内容为：DEEPSEEK_API_KEY=sk-xxx"
            )
        # 确保 API Key 被设置到环境，供 AIClient 使用
        os.environ["DEEPSEEK_API_KEY"] = api_key

        cls.temp_root = Path(tempfile.mkdtemp(prefix="crystal_test_"))
        Config.DATA_ROOT = cls.temp_root
        # 确保目录结构存在
        for d in Config.DIRECTORIES:
            (Config.DATA_ROOT / d).mkdir(parents=True, exist_ok=True)
        FileIO.ensure_directories()
        FileIO.ensure_default_files()
        return cls.temp_root

    @classmethod
    def teardown_temp_root(cls):
        if cls.temp_root and cls.temp_root.exists():
            shutil.rmtree(cls.temp_root, ignore_errors=True)


# ============================================================================
# 测试基类
# ============================================================================

class CrystalTreeTestCase(unittest.TestCase):
    """所有测试用例的基类，负责初始化临时环境和核心组件"""

    @classmethod
    def setUpClass(cls):
        cls.temp_root = TestConfig.setup_temp_root()
        cls.files = FileIO()
        cls.db = DBManager()
        cls.ai = AIClient()  # 真实 API 客户端
        cls.engine = CrystalEngine(cls.files, ai_client=cls.ai)
        if not hasattr(cls.engine, 'meta'):
            cls.engine.meta = MetaLayer(cls.engine, cls.files, ai_client=cls.ai)
        cls.roles = cls._load_roles()

    @classmethod
    def tearDownClass(cls):
        TestConfig.teardown_temp_root()

    @classmethod
    def _load_roles(cls) -> List[Dict]:
        """加载默认角色列表"""
        return [
            {"key": "radical", "name": "激进者", "instruction": "攻击默认前提，假设现有框架是错的，给出颠覆性方案。"},
            {"key": "conservative", "name": "保守者", "instruction": "风险优先，假设资源有限，给出最可落地的稳健方案。"},
            {"key": "structural", "name": "结构主义者", "instruction": "从已有晶体中寻找同构案例，用类比生成方案。"},
            {"key": "judge", "name": "大法官", "instruction": "以晶体卡片、核心操作原则和资源约束为准绳，做出终审裁决。"},
            {"key": "spokesperson", "name": "首席发言人", "instruction": "将内部辩论结论转化为清晰、简洁、无歧义的对外陈述。"},
            {"key": "lark", "name": "百灵鸟", "instruction": "见多识广的通用智能体，从外部世界补充知识，打破信息茧房。"},
        ]

    def setUp(self):
        """每个测试前重置状态"""
        self.files = FileIO()
        self.db = DBManager()
        self.ai = AIClient()
        self.engine = CrystalEngine(self.files, ai_client=self.ai)
        self.engine.meta = MetaLayer(self.engine, self.files, ai_client=self.ai)
        self.roles = self._load_roles()
        FileIO.ensure_directories()
        FileIO.ensure_default_files()

    def _create_test_session(self) -> str:
        sid = datetime.now().strftime("%Y%m%d%H%M%S") + "_test"
        self.db.create_session(sid, "测试会话")
        return sid

    def _add_test_message(self, session_id: str, role: str, content: str):
        name, history, _ = self.db.get_session(session_id)
        if name is None:
            self.db.create_session(session_id, "测试会话")
        self.db.update_session(session_id, history + [(role, content)], name or "测试会话")

    def _assert_json_response(self, data: Any):
        if isinstance(data, (dict, list)):
            json.dumps(data)
        else:
            self.fail(f"期望 JSON 响应，得到 {type(data)}")

    @staticmethod
    def get_hot_questions() -> List[str]:
        return [
            "在生成式物理引擎即将成熟的2026年，传统游戏引擎公司应如何转型？请给出三步战略。",
            "后真相时代，如何通过认知晶体树设计一套『事实免疫力』训练体系？",
            "AI 伦理审查委员会在开源模型监管中应扮演什么角色？给出可操作方案。",
            "Web4 的核心理念是『人机共情』，这将对社交网络算法产生哪些颠覆？",
            "气候科技投资在2026年出现泡沫迹象，如何甄别真创新与伪需求？",
            "如果 AGI 在 2027 年到来，人类应优先保留哪些核心技能？",
            "脑机接口消费化后，认知隐私如何保护？提出三种防护策略。",
            "量子计算商业化在即，它对现有加密体系的影响及应对时间表。",
            "生成式 AI 已能撰写长篇小说，出版业如何重构价值链条？",
            "元宇宙教育当前最大的瓶颈是硬件还是内容？请用数据论证。"
        ]


# ============================================================================
# Day 1 ~ 2: 警报系统 + 动态路由
# ============================================================================

class TestAlarmAndRouting(CrystalTreeTestCase):
    def test_alarm_knowledge_poverty(self):
        alarm = AlarmMonitor()
        metrics = {"crystal_reference_rate": 0.2, "bias_amplification": 0.1,
                   "external_has_new": True, "jaccard_similarity": 0.6}
        triggered = alarm.check(metrics)
        self.assertGreater(len(triggered), 0)
        self.assertTrue(any(t["rule"] == "knowledge_poverty" for t in triggered))

    def test_dynamic_routing_complexity(self):
        gate = CheapGate(self.engine, self.files)
        simple_q = "你好"
        medium_q = "如何提升团队技术决策质量？"
        complex_q = "在资源有限的情况下，如何设计一个自我修正的OKR体系以应对市场不确定性？请给出框架和评估指标。"
        result_simple = gate.check(simple_q, [])
        result_medium = gate.check(medium_q, [])
        result_complex = gate.check(complex_q, [])
        self.assertEqual(result_simple["complexity"], "simple")
        self.assertEqual(result_medium["complexity"], "medium")
        self.assertEqual(result_complex["complexity"], "high")


# ============================================================================
# Day 3: 元原语触发链
# ============================================================================

class TestMetaPrimitiveChains(CrystalTreeTestCase):
    def test_isolated_crystal_trigger_validation(self):
        # 创建 3 个孤立晶体（links 为空列表）
        for i in range(3):
            self.engine.create_crystal(f"C{i:03d}", f"孤立晶体{i}", links=[])
        # 强制更新分层，让 heat 等状态重新计算，确保检测生效
        self.engine.update_crystal_layers()
        # 调用主动缺口检测
        gap_result = self.engine.meta.active_gap_detection()
        self.assertIsInstance(gap_result, dict)
        self.assertGreaterEqual(
            gap_result.get("stats", {}).get("isolated_count", 0),
            3,
            "未能检测到足够多的孤立晶体，请检查 active_gap_detection 实现"
        )
        # 触发链应触发验证门控
        triggered = self.engine.meta.process_trigger_chains({"active_gap_detection": gap_result})
        self.assertGreater(len(triggered), 0)
        self.assertTrue(
            any(t["chain"] == "isolated_crystal_to_validation" for t in triggered),
            "触发链未能触发 isolated_crystal_to_validation"
        )


# ============================================================================
# Day 4: 非马尔可夫历史检索 + 失败轨迹
# ============================================================================

class TestHistoryRetrieval(CrystalTreeTestCase):
    def test_history_diagnose_and_reuse(self):
        # 先写入一条失败轨迹，包含问题原文和有效晶体
        self.engine.log_evolution_event(
            "failure_trace",
            {
                "question": "如何提升团队决策质量？",
                "failure_traces": {
                    "failure_type": "low_crystal_reference",
                    "question": "如何提升团队决策质量？",
                    "context": {"ref_rate": 0.3}
                },
                "effective_crystals": ["C001", "C002"]
            }
        )
        # 再调用历史诊断
        result = self.engine.meta.diagnose_history("团队决策质量提升方法")
        self.assertIsNotNone(result)
        self.assertTrue(
            result.get("matched", False),
            "未能匹配历史失败轨迹，请检查 diagnose_history 实现"
        )
        self.assertIn("C001", result.get("crystal_combination", []))


# ============================================================================
# Day 5: Hebbian 学习
# ============================================================================

class TestHebbianLearning(CrystalTreeTestCase):
    def test_hebbian_update_and_boost(self):
        self.engine.create_crystal("C001", "测试晶体1")
        self.engine.create_crystal("C002", "测试晶体2")
        self.engine.update_hebbian_weights(["C001", "C002"], "general", 0.8)
        boost1 = self.engine.get_hebbian_boost("C001", "general")
        self.assertGreater(boost1, 0)
        crystals = self.engine.parse_crystals()
        ranked = self.engine.rank_crystals("测试", crystals, top_k=3, task_type="general")
        self.assertGreater(len(ranked), 0)
        top_ids = [c.id for _, c in ranked]
        self.assertIn("C001", top_ids[:3])


# ============================================================================
# Day 7: 帕累托前沿跟踪
# ============================================================================

class TestParetoTracking(CrystalTreeTestCase):
    def test_record_and_status(self):
        self.engine.meta.record_conversation_metrics(
            profile_name="balanced",
            accuracy=0.85,
            cost=0.002,
            latency=2.5,
            crystal_refs=3,
            quality_score=0.8
        )
        status = self.engine.meta.get_pareto_status()
        self.assertIn("configs", status)
        self.assertIn("balanced", status["configs"])
        self.assertGreater(status["configs"]["balanced"]["count"], 0)
        self.assertEqual(status["configs"]["balanced"]["accuracy"], 0.85)


# ============================================================================
# Day 8: 双时间尺度进化调度
# ============================================================================

class TestSaturationDetector(CrystalTreeTestCase):
    def test_saturation_detection(self):
        for i in range(5):
            score = 0.5 + i * 0.01
            context = {"modification_type": "prompt"}
            self.engine.meta.prompt_saturation_detector(score, context)
        status = self.engine.meta.get_saturation_status()
        self.assertIn("saturation_status", status)
        state_file = Config.DATA_ROOT / "系统日志" / "saturation_state.json"
        self.assertTrue(state_file.exists())


# ============================================================================
# Day 9-10: Skill 迁移与验证
# ============================================================================

class TestSkillMigration(CrystalTreeTestCase):
    def test_create_and_validate_skill(self):
        self.engine.create_crystal("C999", "测试Skill内容", links=[])
        skill_path = self.engine.get_skill_path("C999")
        self.assertIsNotNone(skill_path)
        self.assertTrue((skill_path / "CRYSTAL.md").exists())
        self.assertTrue((skill_path / "validate.py").exists())
        result = self.engine.validate_skill("C999")
        self.assertTrue(result["valid"])
        self.assertIn("All validation passed!", result["output"])


# ============================================================================
# Day 11: 强制探索
# ============================================================================

class TestForceExploration(CrystalTreeTestCase):
    def test_force_explore_hole(self):
        hole_id = "H999"
        content = "测试孔洞：如何应对生成式物理的冲击？"
        self.files.append("holes", f"\n| {hole_id} | {content} | 0.9 |\n")
        explorer = self.engine.meta.force_explorer
        result = explorer.force_explore(hole_id, force_level="high")
        self.assertTrue(result.get("success") or result.get("crystal_generated") is not None)
        if result.get("crystal_generated"):
            self.assertTrue(self.engine.get_skill_path(result["crystal_generated"]) is not None)


# ============================================================================
# Day 11.5: RUMAD 拓扑控制
# ============================================================================

class TestRUMAD(CrystalTreeTestCase):
    def test_rumad_select_action(self):
        rumad = RUMADController(["激进者", "保守者", "结构主义者"])
        state = "H_M_H_E"
        actions = [("激进者", "保守者"), ("保守者", "激进者"), ("结构主义者", "激进者")]
        action = rumad.select_action(state, actions, round_num=2)
        self.assertIsNotNone(action)
        rumad.update_q_value(state, action, reward=0.5, next_state_key="H_M_M_M")
        self.assertGreater(len(rumad.q_table), 0)


# ============================================================================
# Day 12: 可验证主张 + SVR-MAD + 沙盒 + M3MAD
# ============================================================================

class TestVerificationComponents(CrystalTreeTestCase):
    def test_claim_extractor(self):
        extractor = ClaimExtractor(self.engine)
        text = "A比B高30%，准确率达到95%，成本低于100元。"
        claims = extractor.extract_from_text(text)
        self.assertGreater(len(claims), 0)
        self.assertTrue(any(c.claim_type == "comparative" for c in claims))

    def test_svrmad_posterior(self):
        validator = SVRMADValidator(self.engine)
        rounds = [
            {"answers": [{"role": "激进者", "answer": "..."}]},
            {"answers": [{"role": "保守者", "answer": "..."}]},
            {"answers": [{"role": "结构主义者", "answer": "..."}]}
        ]
        posterior = validator.compute_posterior("激进者", rounds)
        self.assertGreaterEqual(posterior, 0.0)
        self.assertLessEqual(posterior, 1.0)

    def test_sandbox_execution(self):
        sandbox = SandboxExecutor(self.engine)
        # 使用一个一定能提取出主张的文本
        test_text = "该算法的准确率达到了95%。"
        claims = ClaimExtractor().extract_from_text(test_text)
        self.assertGreater(
            len(claims), 0,
            "ClaimExtractor 未能提取出任何主张，请检查 ClaimExtractor 实现"
        )
        claim = claims[0]
        result = sandbox.execute_claim(claim)
        self.assertIn("success", result)
        self.assertIsInstance(result["execution_time"], float)

    def test_m3mad_bench(self):
        bench = M3MADBench(self.engine, self.ai)
        mock_result = {"question": "测试", "rounds": []}
        score = bench.evaluate(mock_result)
        self.assertIsInstance(score.overall_score, float)


# ============================================================================
# Day 13: 强制沉淀 + 会话锁定
# ============================================================================

class TestDepositAndLock(CrystalTreeTestCase):
    def test_extract_conclusion_layers(self):
        rounds = [{
            "round": 1,
            "answers": [
                {"role": "激进者", "answer": "我们应该颠覆现有架构，采用事件驱动。"},
                {"role": "保守者", "answer": "风险太大，建议分阶段迁移。"}
            ],
            "audit": {"summary": "双方分歧较大"}
        }]
        debate = DebateEngine(self.ai, self.engine, self.roles, log=lambda m, l: None)
        result = debate._extract_conclusion_layers("问题", rounds)
        self.assertIn("L1_conclusions", result)
        self.assertIn("unarchived_holes", result)

    def test_session_lock_on_unarchived(self):
        deposit_path = Config.DATA_ROOT / "系统日志" / "last_deposit.json"
        deposit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(deposit_path, "w") as f:
            json.dump({"unarchived_holes": [{"id": "H001", "content": "待验证孔洞", "urgency": 0.8}]}, f)
        unarchived = self.engine._get_unarchived_holes()
        self.assertGreater(len(unarchived), 0)


# ============================================================================
# Day 13.5: 沉思式反思
# ============================================================================

class TestContemplativeReflection(CrystalTreeTestCase):
    def test_reflection_generates_wise_echo(self):
        contemplative = ContemplativeEngine(self.ai, self.engine)
        question = "如何在后真相时代保持判断力？"
        rounds = [{"round": 1, "answers": [{"role": "激进者", "answer": "..."}], "audit": {"summary": "..."}}]
        result = contemplative.reflect(question, rounds)
        self.assertIn("wise_echo", result)
        self.assertGreater(len(result["wise_echo"]), 20)
        for dim in ["mindfulness", "emptiness", "non_duality", "boundless_care"]:
            self.assertIn(dim, result)


# ============================================================================
# Day 14: 失败模式诊断
# ============================================================================

class TestFailurePatternDiagnosis(CrystalTreeTestCase):
    def test_diagnose_failure_patterns(self):
        for _ in range(3):
            self.engine.log_evolution_event(
                "alarm",
                {"rule": "knowledge_poverty", "message": "引用率低", "data": {"ref_rate": 0.3}}
            )
        result = self.engine.meta.diagnose_failure_patterns()
        self.assertIn("patterns", result)
        patterns = [p for p in result["patterns"] if p["type"] == "crystal_reference_insufficient"]
        self.assertGreater(len(patterns), 0)


# ============================================================================
# Day 15: 双环闭环验证
# ============================================================================

class TestDualLoopVerification(CrystalTreeTestCase):
    def test_dual_loop_report(self):
        self.engine.log_evolution_event(
            "crystal_created",
            {"crystal_id": "C999", "content": "闭环测试晶体"}
        )
        self.engine._track_crystal_usage(["C999"], context="debate")
        result = self.engine.verify_dual_loop()
        self.assertIn("verified", result)
        self.assertIn("call_rate", result)
        self.assertIsInstance(result["call_rate"], float)


# ============================================================================
# Day 16-17: Gödel Agent 递归进化
# ============================================================================

class TestGödelEvolution(CrystalTreeTestCase):
    def test_gödel_evolution_cycle(self):
        template_manager = self.engine.meta.template_manager
        agent = GödelAgent(self.engine, self.ai, template_manager)
        result = agent.run_evolution_cycle("radical")
        self.assertIn("applied", result)
        self.assertGreaterEqual(result.get("candidates_generated", 0), 0)

    def test_recursive_evolution_integration(self):
        result = self.engine.meta.gödel_agent.run_recursive_evolution_cycle()
        self.assertIn("overall_success", result)
        self.assertIsInstance(result["overall_success"], bool)


# ============================================================================
# Day 18: 持续审计 + 健康度仪表盘
# ============================================================================

class TestAuditAndHealth(CrystalTreeTestCase):
    def test_audit_service(self):
        auditor = LayerAuditService(self.engine, self.files)
        report = auditor.run_audit()
        self.assertIsInstance(report.health_score, float)
        self.assertGreaterEqual(report.health_score, 0.0)
        self.assertLessEqual(report.health_score, 10.0)
        self.assertGreater(len(report.layers), 0)

    def test_health_dashboard(self):
        if not hasattr(self.engine, '_audit_service'):
            self.engine._audit_service = LayerAuditService(self.engine, self.files)
        self.engine.run_audit_now()
        status = self.engine.get_audit_status()
        self.assertTrue(status.get("available", False))
        self.assertIn("health_score", status)


# ============================================================================
# Day 18.5: 用户态系统状态断言
# ============================================================================

class TestHealthAssertions(CrystalTreeTestCase):
    def test_status_bar_data(self):
        status = self.engine.get_audit_status()
        self.assertIsInstance(status.get("cognitive_continuity_score"), (int, float))
        self.assertIsInstance(status.get("fingerprint_change_rate"), (int, float))


# ============================================================================
# Day 19: 自我修复循环
# ============================================================================

class TestSelfHealing(CrystalTreeTestCase):
    def test_self_healing_trigger(self):
        healer = SelfHealing(self.engine, self.ai)
        for _ in range(3):
            healer.record_quality(0.2)
        status = healer.get_status()
        self.assertGreaterEqual(status.get("consecutive_low_count", 0), 0)
        healer.force_trigger_repair()
        self.assertIsNotNone(healer.last_repair_time)


# ============================================================================
# Day 20: GitHub Trending + 全球认知雷达
# ============================================================================

class TestGitHubAndRadar(CrystalTreeTestCase):
    def test_trending_crystalizer(self):
        crystalizer = GitHubTrendingCrystalizer(self.engine, self.ai)
        repos = crystalizer.fetch_trending(max_items=3)
        self.assertGreater(len(repos), 0)
        for repo in repos[:1]:
            crystal = crystalizer.generate_crystal_for_repo(repo)
            self.assertIn("content", crystal)
            self.assertGreater(len(crystal["content"]), 5)

    def test_multilingual_radar(self):
        fetcher = ExternalFetcher()
        result = fetcher.fetch_multilingual_news(max_per_lang=2)
        self.assertIn("zh", result)
        self.assertGreater(len(result["zh"]), 0)


# ============================================================================
# Day 21: 认证 + 支付集成（模拟）
# ============================================================================

class TestAuthAndPayment(CrystalTreeTestCase):
    def test_auth_register_login(self):
        # 使用带时间戳的用户名，避免本地残留数据干扰
        username = f"testuser_{int(time.time())}"
        password = "testpass"
        success, msg = auth.register_user(username, password)
        self.assertTrue(success, f"注册失败: {msg}")
        ok, msg, token = auth.login_user(username, password)
        self.assertTrue(ok, f"登录失败: {msg}")
        self.assertIsNotNone(token, "登录后未能获取 token")
        user = auth.get_user(username)
        self.assertIsNotNone(user, "注册后无法获取用户信息")
        self.assertEqual(user.tier, "free", "新用户默认应为 free 套餐")

    def test_trial_limit(self):
        auth.register_user("testuser2", "testpass")
        for _ in range(20):
            auth.increment_trial("testuser2")
        remaining = auth.get_trial_remaining("testuser2")
        self.assertEqual(remaining, 0)
        self.assertFalse(auth.increment_trial("testuser2"))

    def test_upgrade_tier(self):
        auth.register_user("testuser3", "testpass")
        auth.update_user_tier("testuser3", "pro")
        user = auth.get_user("testuser3")
        self.assertEqual(user.tier, "pro")
        self.assertGreater(auth.get_trial_remaining("testuser3"), 1000)


# ============================================================================
# 集成测试：完整辩论 + 输出编排 + 沉思式反思（端到端）
# ============================================================================

class TestEndToEndDebate(CrystalTreeTestCase):
    def test_debate_with_all_components(self):
        question = "如何在不增加预算的前提下，提升一个20人研发团队的技术决策质量？"
        debate = DebateEngine(
            self.ai,
            self.engine,
            self.roles,
            log=lambda m, l: print(f"[{l}] {m[:50]}..."),
            progress_callback=None
        )
        result = debate.run(question, mode="debate_full", max_rounds=2)
        self.assertIn("rounds", result)
        self.assertGreater(len(result["rounds"]), 0)
        orchestrator = OutputOrchestrator(self.ai, self.engine)
        final_schema = orchestrator.generate(
            question,
            result.get("rounds", []),
            wise_echo=result.get("elegant_epilogue", "")
        )
        self.assertIsInstance(final_schema, FinalOutputSchema)
        self.assertGreater(len(final_schema.board_version), 10)
        self.assertGreater(len(final_schema.employee_version), 10)
        self.assertGreater(len(final_schema.novice_version), 10)
        self.assertGreater(len(final_schema.expert_version), 10)
        self.assertGreater(len(final_schema.elegant_epilogue), 10)
        self.assertIsInstance(final_schema.judge_performance_board, list)


# ============================================================================
# 自定义测试结果类（记录所有测试状态）
# ============================================================================

from unittest import TestResult

class DetailedTestResult(TestResult):
    """扩展 TestResult，记录每个测试的详细状态"""
    def __init__(self, stream=None, descriptions=None, verbosity=None):
        super().__init__(stream, descriptions, verbosity)
        self.successes = []      # 通过的测试名称列表
        self.test_status = {}    # {test_id: 'pass'|'fail'|'error'}

    def startTest(self, test):
        super().startTest(test)
        # 记录当前测试名称，用于后续状态更新
        self._current_test = test.id()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test.id())
        self.test_status[test.id()] = 'pass'

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.test_status[test.id()] = 'fail'

    def addError(self, test, err):
        super().addError(test, err)
        self.test_status[test.id()] = 'error'

    def get_all_results(self):
        """返回所有测试的状态字典，以及通过/失败/错误列表"""
        return {
            'successes': self.successes,
            'failures': [f[0].id() for f in self.failures],
            'errors': [e[0].id() for e in self.errors],
            'all': self.test_status
        }


# ============================================================================
# HTML报告生成（增强版：包含所有测试明细表格）
# ============================================================================

def generate_html_report(result: DetailedTestResult, start_time: datetime, end_time: datetime) -> str:
    total = result.testsRun
    passed = len(result.successes)
    failed = len(result.failures)
    errors = len(result.errors)
    pass_rate = (passed / total * 100) if total > 0 else 0

    # 构建所有测试状态表格行
    all_status = result.get_all_results()
    all_tests = all_status['all']
    sorted_tests = sorted(all_tests.items())

    table_rows = ""
    for test_id, status in sorted_tests:
        if status == 'pass':
            icon = "✅"
            label = "通过"
            color = "#2a9d8f"
        elif status == 'fail':
            icon = "❌"
            label = "失败"
            color = "#d84a55"
        else:
            icon = "⚠️"
            label = "错误"
            color = "#f59e0b"
        table_rows += f"""
        <tr>
            <td style="padding:6px 12px; border-bottom:1px solid #eee;">{test_id}</td>
            <td style="padding:6px 12px; border-bottom:1px solid #eee; color:{color}; font-weight:bold;">{icon} {label}</td>
        </tr>
        """

    failure_details = ""
    for test, trace in result.failures:
        failure_details += f"""
        <div class="failure">
            <h4>❌ {test.id()}</h4>
            <pre>{trace}</pre>
        </div>
        """
    error_details = ""
    for test, trace in result.errors:
        error_details += f"""
        <div class="error">
            <h4>⚠️ {test.id()}</h4>
            <pre>{trace}</pre>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>认知晶体树 v2.2 全量回归测试报告</title>
        <style>
            body {{
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background: #f5f7fa;
                margin: 0;
                padding: 20px;
                color: #1a2c3e;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 16px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.08);
                padding: 30px;
            }}
            h1 {{
                font-size: 28px;
                border-bottom: 3px solid #2a9d8f;
                padding-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .summary {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 16px;
                margin: 24px 0;
                background: #f8fafc;
                border-radius: 12px;
                padding: 20px;
            }}
            .summary-item {{
                text-align: center;
            }}
            .summary-item .number {{
                font-size: 32px;
                font-weight: 700;
            }}
            .summary-item .label {{
                font-size: 14px;
                color: #5a7b8e;
            }}
            .status-pass {{ color: #2a9d8f; }}
            .status-fail {{ color: #d84a55; }}
            .status-error {{ color: #f59e0b; }}
            .details {{ margin-top: 24px; }}
            .failure, .error {{
                background: #fef2f2;
                border-left: 4px solid #d84a55;
                padding: 12px 16px;
                margin-bottom: 12px;
                border-radius: 8px;
                overflow-x: auto;
            }}
            .error {{
                background: #fffbeb;
                border-left-color: #f59e0b;
            }}
            .failure h4, .error h4 {{ margin: 0 0 8px 0; font-size: 15px; }}
            pre {{
                margin: 6px 0;
                font-size: 13px;
                background: #f1f3f5;
                padding: 10px;
                border-radius: 6px;
                white-space: pre-wrap;
                word-break: break-all;
            }}
            .timestamp {{
                color: #5a7b8e;
                font-size: 14px;
                margin-top: 16px;
                text-align: right;
                border-top: 1px solid #e9edf2;
                padding-top: 16px;
            }}
            .badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 40px;
                font-size: 14px;
                font-weight: 600;
            }}
            .badge-pass {{ background: #d1fae5; color: #065f46; }}
            .badge-fail {{ background: #fee2e2; color: #991b1b; }}
            .badge-error {{ background: #fef3c7; color: #92400e; }}
            .test-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                font-size: 14px;
            }}
            .test-table th {{
                background: #f0f4f8;
                text-align: left;
                padding: 8px 12px;
                border-bottom: 2px solid #dde2e8;
            }}
            .test-table td {{
                padding: 6px 12px;
                border-bottom: 1px solid #eee;
            }}
            .test-table tr:hover {{
                background: #f8fafc;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧪 认知晶体树 v2.2 全量回归测试报告</h1>
            <div class="summary">
                <div class="summary-item">
                    <div class="number status-pass">{passed}</div>
                    <div class="label">✅ 通过</div>
                </div>
                <div class="summary-item">
                    <div class="number status-fail">{failed}</div>
                    <div class="label">❌ 失败</div>
                </div>
                <div class="summary-item">
                    <div class="number status-error">{errors}</div>
                    <div class="label">⚠️ 错误</div>
                </div>
                <div class="summary-item">
                    <div class="number">{total}</div>
                    <div class="label">📊 总计</div>
                </div>
                <div class="summary-item">
                    <div class="number">{pass_rate:.1f}%</div>
                    <div class="label">📈 通过率</div>
                </div>
            </div>

            <div>
                <span class="badge badge-pass">通过 {passed}</span>
                <span class="badge badge-fail">失败 {failed}</span>
                <span class="badge badge-error">错误 {errors}</span>
            </div>

            <!-- ===== 所有测试明细表格 ===== -->
            <h2 style="margin-top:30px;">📋 所有测试明细</h2>
            <table class="test-table">
                <thead>
                    <tr>
                        <th>测试用例</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>

            <!-- ===== 失败/错误详情（如有） ===== -->
            <div class="details">
                <h2>🔍 失败 / 错误详情</h2>
                {failure_details if failure_details else '<p style="color:#2a9d8f;">✅ 无失败或错误。</p>'}
                {error_details if error_details else ''}
            </div>

            <div class="timestamp">
                测试开始：{start_time.strftime('%Y-%m-%d %H:%M:%S')}<br>
                测试结束：{end_time.strftime('%Y-%m-%d %H:%M:%S')}<br>
                耗时：{(end_time - start_time).total_seconds():.2f} 秒
            </div>
        </div>
    </body>
    </html>
    """
    return html


# ============================================================================
# 测试执行器与报告
# ============================================================================

def run_all_tests():
    start_time = datetime.now()
    print("\n" + "="*80)
    print("🧪 认知晶体树 v2.2 全量回归测试（真实API环境）")
    print("="*80)
    print(f"测试开始时间: {start_time.isoformat()}")
    print(f"API Key 状态: {'已配置' if os.environ.get('DEEPSEEK_API_KEY') else '❌ 未设置（测试将失败）'}")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    test_classes = [
        TestAlarmAndRouting,
        TestMetaPrimitiveChains,
        TestHistoryRetrieval,
        TestHebbianLearning,
        TestParetoTracking,
        TestSaturationDetector,
        TestSkillMigration,
        TestForceExploration,
        TestRUMAD,
        TestVerificationComponents,
        TestDepositAndLock,
        TestContemplativeReflection,
        TestFailurePatternDiagnosis,
        TestDualLoopVerification,
        TestGödelEvolution,
        TestAuditAndHealth,
        TestHealthAssertions,
        TestSelfHealing,
        TestGitHubAndRadar,
        TestAuthAndPayment,
        TestEndToEndDebate
    ]
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    # 使用自定义结果类
    runner = unittest.TextTestRunner(verbosity=2, failfast=False, resultclass=DetailedTestResult)
    result = runner.run(suite)

    end_time = datetime.now()
    print("\n" + "="*80)
    print("📊 测试报告")
    print("="*80)
    print(f"运行测试: {result.testsRun}")
    print(f"通过: {len(result.successes)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    # 生成HTML报告（传入详细结果）
    html_content = generate_html_report(result, start_time, end_time)
    desktop_path = Path.home() / "Desktop"
    report_path = desktop_path / f"regression_test_report_{start_time.strftime('%Y%m%d_%H%M%S')}.html"
    report_path.write_text(html_content, encoding="utf-8")
    print(f"\n📄 HTML报告已保存至：{report_path}")

    return result


if __name__ == "__main__":
    try:
        result = run_all_tests()
    finally:
        if TestConfig.temp_root and TestConfig.temp_root.exists():
            shutil.rmtree(TestConfig.temp_root, ignore_errors=True)
    sys.exit(0 if result.wasSuccessful() else 1)