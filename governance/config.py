#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

class Config:
    DATA_ROOT: Path = Path(os.getenv("CRYSTAL_TREE_DATA_ROOT", str(PROJECT_ROOT))).absolute()
    OUTPUT_DIR: Path = PROJECT_ROOT / "docs" / "输出"
    REPORT_OUTPUT_DIR: Path = PROJECT_ROOT / "docs" / "输出" / "报告"
    UPLOAD_DIR: Path = PROJECT_ROOT / "docs" / "输出" / "上传"
    SCORE_OUTPUT_DIR: Path = PROJECT_ROOT / "docs" / "输出" / "评分"
    ATTENTION_LIMIT: int = 50
    L0_SIZE: int = 3
    L1_MAX: int = 47
    L1_WARNING_THRESHOLD: int = 45
    L2_TO_L3_HEAT_THRESHOLD: float = 0.1
    L2_TO_L3_DAYS_THRESHOLD: int = 30
    # TIMEOUT: tuple = (15, 30)   # 连接15秒，读取30秒（太短）
    TIMEOUT: tuple = (30, 120)     # 连接30秒，读取120秒（给长文本生成留足时间）
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 1.5
    DELAY_BETWEEN_REQUESTS: tuple = (1, 3)
    DAILY_PLAN_TIME_BUDGET_SECONDS: int = 900
    DAILY_PLAN_MAX_CANDIDATES: int = 60
    DAILY_PLAN_TOP_ITEMS: int = 15
    DAILY_PLAN_MAX_PENDING_CARDS: int = 10
    # 在 Config 类中新增
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")  # 月付订阅价格ID
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"
    # DeepSeek V4 Flash 官方价（每百万 token，美元）；如实际模型/价格不同可用环境变量覆盖
    DEEPSEEK_INPUT_MISS_PRICE_PER_M: float = float(os.getenv("DEEPSEEK_INPUT_MISS_PRICE_PER_M", "0.14"))
    DEEPSEEK_INPUT_HIT_PRICE_PER_M: float = float(os.getenv("DEEPSEEK_INPUT_HIT_PRICE_PER_M", "0.0028"))
    DEEPSEEK_OUTPUT_PRICE_PER_M: float = float(os.getenv("DEEPSEEK_OUTPUT_PRICE_PER_M", "0.28"))
    BAIDU_API_KEY: str = os.getenv("BAIDU_API_KEY", "")
    BAIDU_APPBUILDER_API_KEY: str = os.getenv("BAIDU_APPBUILDER_API_KEY", "")
    ENABLE_BAIDU_QIANFAN: bool = os.getenv("ENABLE_BAIDU_QIANFAN", "") in ("1", "true", "True")
    QIANFAN_OVERVIEW_MODE: str = os.getenv("QIANFAN_OVERVIEW_MODE", "synthesized")
    QIANFAN_TIMEOUT: tuple = (10, 90)
    SEARCH_PROVIDER_TIMEOUTS: dict = {
        "baidu_qianfan": (10, 90),
        "arxiv": (10, 120),
        "semantic_scholar": (10, 30),
    }
    SEARCH_TOTAL_TIMEOUT_SECONDS: int = 180
    BAIDU_SEARCH_API_URL: str = os.getenv(
        "BAIDU_SEARCH_API_URL",
        "https://qianfan.baidubce.com/v2/ai_search/web_summary",
    )
    BAIDU_SEARCH_CHAT_URL: str = os.getenv(
        "BAIDU_SEARCH_CHAT_URL",
        "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
    )
    JINA_READER_URL: str = "https://r.jina.ai/"
    ARXIV_MIRRORS: list = ["https://cn.arxiv.org", "https://arxiv.org"]
    HF_MIRROR: str = "https://hf-mirror.com"
    PATHS: dict = {
        "state": "系统日志/状态快照.md",
        "crystals": "晶体数据/晶体卡片.md",
        "holes": "晶体数据/孔洞分层.md",
        "principles": "核心配置/核心操作原则.md",
        "ai_instructions": "核心配置/AI协作者指令.md",
        "pending": "暂存区/PENDING_待确认卡片.md",
        "search_cache": "系统日志/搜索摘要.md",
        "change_log": "系统日志/变更记录.md",
        "layer_state": "系统日志/晶体分层.json",
        "hole_progress": "系统日志/孔洞进度.json",
        "external_cache": "系统日志/external_sources_cache.json",
        "fingerprint": "系统日志/user_profile.json",  # ★ 新增这一行
        "task_cards": "系统日志/任务卡片.json",
        "roles": "核心配置/角色定义.json",
        "pareto_frontier": "系统日志/pareto_frontier.json",
        "inspiration_pool": "系统日志/灵感池.json",
    }
    DIRECTORIES: list = ["晶体数据", "核心配置", "系统日志", "暂存区", "系统日志/案例"]
    USER_AGENTS: list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
    ]
    GUI_BG_MAIN: str = "#f7f3ff"
    GUI_BG_SIDEBAR: str = "#fbf8ff"
    GUI_BG_CARD: str = "#fffaff"
    GUI_BG_CARD_ALT: str = "#f4efff"
    GUI_BG_INPUT: str = "#fffefe"
    GUI_BG_HEADER: str = "#f1ebff"
    GUI_FG_TEXT: str = "#211b33"
    GUI_FG_MUTED: str = "#716883"
    GUI_BORDER: str = "#d9cdf5"
    GUI_BORDER_STRONG: str = "#bba9ea"
    GUI_ACCENT: str = "#6f56d9"
    GUI_ACCENT_DARK: str = "#503bb4"
    GUI_SUCCESS: str = "#5f9f45"
    GUI_WARNING: str = "#dc8425"
    GUI_DANGER: str = "#d84a55"
    GUI_INFO: str = "#8d7fd1"
    GUI_BUTTON_SOFT: str = "#eee8fb"
    GUI_HIGHLIGHT: str = "#e7ddff"
    GUI_TITLE_FONT: tuple = ("微软雅黑", 18, "bold")
    GUI_CARD_FONT: tuple = ("微软雅黑", 11, "bold")
    GUI_BUTTON_FONT: tuple = ("微软雅黑", 10)
    GUI_TEXT_FONT: tuple = ("微软雅黑", 10)
    GUI_INPUT_FONT: tuple = ("微软雅黑", 11)
    GUI_LOG_FONT: tuple = ("宋体", 12)

    # ===== 向量检索配置 =====
    VECTOR_SEARCH_ENABLED: bool = False
    VECTOR_SEARCH_MODEL: str = "all-MiniLM-L6-v2"
    VECTOR_SEARCH_TOP_K: int = 5
    VECTOR_SEARCH_BM25_FALLBACK: bool = True  # 向量检索失败时降级到 BM25

    # ===== 验证门控配置 =====
    VALIDATION_GATE_RULES: dict = {
        "min_references": 2,           # 最少被引用的晶体数
        "require_external_source": False,  # 是否要求外部来源
        "require_recent_access": True,     # 是否要求近期访问
        "recent_access_days": 60,          # 近期访问天数阈值
        "low_contribution_threshold": 25.0, # 低贡献阈值
    }

    # ===== 元层原语开关（建议1：工作层+元层双层架构）=====
    META_PRIMITIVES: dict = {
        "active_gap_detection": {
            "enabled": True,
            "description": "主动缺口检测：自动识别晶体之间的逻辑缝隙"
        },
        "temporal_aware_escalation": {
            "enabled": True,
            "description": "时序感知升级：根据时间戳和活动频率自动调整优先级"
        },
        "layer_aware_calibration": {
            "enabled": True,
            "description": "层级感知校准：根据晶体层级（L1/L2/L3）调整调度权重"
        },
        "sleep_consolidation": {
            "enabled": True,
            "description": "睡眠式巩固：低活跃时段自动进行知识压缩和冗余清理"
        },
        "distributed_metacognition": {
            "enabled": False,
            "description": "分布式元认知：多个系统实例间共享认知模式（需网络）"
        },
        "validation_gated_self_evolution": {
            "enabled": True,
            "description": "验证门控自我进化：任何自我改进必须通过验证门检验"
        },
        # ===== 新增：PEAR 动态角色路由 =====
        "dynamic_role_routing": {
            "enabled": True,
            "description": "PEAR动态角色路由：通过元辩论为每个位置选择最优角色"
        }
    }

    META_LAYER_CONFIG: dict = {
        "consolidation_hour_start": 2,
        "consolidation_hour_end": 4,
        "gap_detection_interval_hours": 6,
        "max_crystals_before_consolidation": 100,
        "validation_gate_rules": [
            "new_evidence_from_at_least_3_sources",
            "audit_score_gt_0.6",
            "no_major_conflict_with_existing_crystals"
        ]
    }
    # ===== Day 21: 用户认证与付费配置 =====
    FREE_TRIAL_LIMIT: int = 20
    SUBSCRIPTION_TIERS: dict = {
        "free": {"label": "免费版", "trial_limit": 20},
        "pro": {"label": "专业版", "trial_limit": 9999},
    }   
       

    # ===== Day 7: 帕累托配置 =====
    PROFILE_HIGH_ACCURACY: dict = {
        "name": "高精度模式",
        "accuracy_weight": 0.7,
        "cost_weight": 0.1,
        "latency_weight": 0.2,
        "max_tokens": 4000,
        "temperature": 0.3,
        "enable_vector_search": True,
        "enable_external_fetch": True,
        "debate_rounds": 4,
        "description": "追求最高答案质量，适合复杂决策问题"
    }
    PROFILE_BALANCED: dict = {
        "name": "平衡模式",
        "accuracy_weight": 0.5,
        "cost_weight": 0.3,
        "latency_weight": 0.2,
        "max_tokens": 2000,
        "temperature": 0.5,
        "enable_vector_search": True,
        "enable_external_fetch": True,
        "debate_rounds": 3,
        "description": "质量与成本的平衡，适合日常使用"
    }
    PROFILE_ECONOMY: dict = {
        "name": "经济模式",
        "accuracy_weight": 0.3,
        "cost_weight": 0.4,
        "latency_weight": 0.3,
        "max_tokens": 800,
        "temperature": 0.7,
        "enable_vector_search": False,
        "enable_external_fetch": False,
        "debate_rounds": 2,
        "description": "最低成本，适合简单问题和快速响应"
    }

    DEFAULT_PROFILE: str = "balanced"
    PARETO_HISTORY_LIMIT: int = 50

    # ===== Day 7: 评分规则配置（可JSON覆盖） =====
    SCORING_RULES: dict = {
        "quality": {
            "crystal_ref_weight": 0.3,
            "jaccard_weight": 0.2,
            "audit_score_weight": 0.3,
            "risk_identified_weight": 0.2
        },
        "thresholds": {
            "excellent": 0.8,
            "good": 0.6,
            "needs_improvement": 0.4
        }
    }
    # ===== Day 3 新增：元原语触发链配置 =====
    META_CHAIN_RULES: dict = {
        # 触发链1：孤立晶体 → 验证门控自我进化
        "isolated_crystal_to_validation": {
            "enabled": True,
            "source_primitive": "active_gap_detection",
            "source_condition": "isolated_crystal_count >= 3",  # 发现3个以上孤立晶体
            "target_primitive": "validation_gated_self_evolution",
            "target_params": {"focus": "isolated_crystals"},
            "description": "发现孤立晶体 → 触发验证门控自我进化"
        },
        # 触发链2：高热度久未访问 → 主动缺口检测
        "stale_hot_to_gap_detection": {
            "enabled": True,
            "source_primitive": "temporal_aware_escalation",
            "source_condition": "stale_hot_count >= 2",  # 发现2个以上高热度久未访问晶体
            "target_primitive": "active_gap_detection",
            "target_params": {"focus": "stale_hot_crystals"},
            "description": "高热度久未访问晶体 → 触发主动缺口检测"
        },
        # 触发链3：验证门控自我进化结果 → 时序感知升级（预留）
        "validation_to_temporal": {
            "enabled": False,  # 默认禁用，Day 3 暂不启用
            "source_primitive": "validation_gated_self_evolution",
            "source_condition": "verification_passed_count >= 2",
            "target_primitive": "temporal_aware_escalation",
            "target_params": {"focus": "verified_crystals"},
            "description": "验证通过数量≥2 → 触发时序感知升级"
        }
    }
    
    # ===== Day 17: 递归进化配置 =====
    RECURSIVE_EVOLUTION_CONFIG: dict = {
        "skill_layer": {
            "max_crystals_per_cycle": 2,
            "min_traces_for_generation": 3,
            "auto_commit_enabled": True
        },
        "manual_layer": {
            "optimization_interval_hours": 24,
            "max_optimizations_per_day": 3
        }
    }
    # ===== Day 18: Harness 分解审计配置 =====
    AUDIT_CONFIG: dict = {
        "enabled": True,
        "interval_hours": 168,  # 每周一次（7天）
        "report_path": "系统日志/层级贡献报告.json",
        "history_limit": 52,    # 保留最近52周数据
        "component_checks": [
            "CrystalEngine",
            "DebateEngine",
            "MetaLayer",
            "CheapGate"
        ],
        "fingerprint_change_threshold": 0.15,  # 15%
        "cognitive_continuity_window": 10,      # 最近10次对话
    }  
    # ===== Day 1 新增：警报规则配置（可JSON覆盖） =====
    ALARM_RULES: dict = {
        "knowledge_poverty": {
            "enabled": True,
            "metric": "crystal_reference_rate",
            "threshold": 0.5,          # 引用率 < 50%
            "action": "inject_external",
            "message": "知识贫瘠警报：晶体引用率低于50%，强制注入外部知识"
        },
        "bias_inflation": {
            "enabled": True,
            "metric": "bias_amplification",
            "threshold": 0.3,
            "action": "inject_perspective",
            "message": "偏见膨胀警报：偏见强化指数超过0.3，强制注入对立视角"
        },
        "information_starvation": {
            "enabled": True,
            "metric": "external_consecutive_empty",
            "threshold": 3,            # 连续3轮无新外部数据
            "action": "trigger_search",
            "message": "信息枯竭警报：连续3轮外部搜索无新数据，强制触发搜索"
        },
        "thought_stagnation": {
            "enabled": True,
            "metric": "jaccard_consecutive_high",
            "threshold": 0.8,
            "consecutive": 3,
            "action": "inject_perspective",
            "message": "思维固化警报：辩论Jaccard相似度连续3轮>0.8，强制注入新视角"
        },
        "evidence_strength": {
            "enabled": True,
            "metric": "evidence_strength",
            "threshold": 0.3,
            "action": "trigger_search",
            "message": "证据强度警报：引用/依据比例低于30%，强制补充外部证据"
        },
        "logic_consistency": {
            "enabled": True,
            "metric": "logic_consistency",
            "threshold": 0.6,
            "action": "inject_perspective",
            "message": "逻辑一致性警报：论证平衡度低于60%，强制注入对立视角"
        },
        "overreach": {
            "enabled": True,
            "metric": "overreach_score",
            "threshold": 0.2,
            "action": "inject_perspective",
            "message": "过度推断警报：强因果/绝对化表达占比过高，强制注入审慎视角"
        },
        "output_reliability": {
            "enabled": True,
            "metric": "reliability_score",
            "threshold": 0.7,
            "action": "review_output",
            "message": "表达可靠性警报：存在截断/占位/错误标记，强制重审输出并注入外部知识"
        }
    }
    # ===== 收敛与上下文压缩参数 =====
    CONVERGENCE_CONFIG: dict = {
        "default_max_rounds": 4,
        "history_max_chars": 15000,
        "history_per_role_min": 1500,
        "history_per_role_max": 1900,
        "role_brief_max_chars": 500,
        "summary_max_chars": 300,
        "summary_min_chars": 50,
        "jaccard_convergence_threshold": 0.50,
    }
    # ===== Day 2: 动态路由配置 =====
    ROUTING_CONFIG = {
        "simple_length_threshold": 5,       # 长度<=5且无复杂词视为简单
        "medium_length_threshold": 30,      # 长度>5且<=30且含关键词视为中等
        "complex_keywords": [
            "设计", "方案", "系统", "模型", "策略", "框架", "博弈", "全球", "长期",
            "多变量", "优化", "权衡", "机制", "制度", "政策", "评估", "比较", "综合",
            "如何", "为什么", "怎样", "怎么", "能否", "是否", "哪些", "什么",  # 开放性问题
        ],
        "token_budget_high": 2000,
        "token_budget_medium": 800,
        "token_budget_simple": 200,
    }
    # ===== Day 10: 角色质量参数配置 =====
    ROLE_QUALITY_CONFIG: dict = {
        "radical": {
            "temperature": 0.80,
            "token_multiplier": 4.0,
            "description": "激进者：高温度鼓励颠覆性思维"
        },
        "conservative": {
            "temperature": 0.40,
            "token_multiplier": 3.0,
            "description": "保守者：低温保证风险判断稳定可靠"
        },
        "structural": {
            "temperature": 0.60,
            "token_multiplier": 3.5,
            "description": "结构主义者：中等温度保证框架严谨"
        },
        "lark": {
            "temperature": 0.75,
            "token_multiplier": 4.0,
            "description": "百灵鸟：略高温度鼓励跨领域联想"
        },
        "pilgrim": {
            "temperature": 0.55,
            "token_multiplier": 3.0,
            "description": "取经者：稳定温度保证长期视角一致"
        },
        "strategist": {
            "temperature": 0.80,
            "token_multiplier": 3.5,
            "description": "奇谋者：高温度鼓励非常规路径"
        },
        "statesman": {
            "temperature": 0.35,
            "token_multiplier": 3.5,
            "description": "延安智者：低温保证实事求是"
        },
        "judge": {
            "temperature": 0.20,
            "token_multiplier": 3.0,
            "description": "大法官：极低温保证裁决一致性"
        },
        "spokesperson": {
            "temperature": 0.65,
            "token_multiplier": 3.0,
            "description": "首席发言人：中低温保证叙事精准"
        },
        "twin": {
            "temperature": 0.60,
            "token_multiplier": 3.5,
            "description": "替身-我：模仿用户思维惯性"
        },
        "default": {
            "temperature": 0.70,
            "token_multiplier": 3.0,
            "description": "默认配置"
        }
        
    }

    # ===== Day 16: Gödel Agent 外部数据模式 =====
    GODEL_USE_MOCK_EXTERNAL: bool = False  # Day 3 强制真实抓取
    GODEL_MOCK_EXTERNAL_DATA: str = """
【外部参考信息（模拟数据 - 仅用于测试评估）】
- [arxiv] 最新研究表明，多角色辩论可提升复杂决策质量约 30%
- [news] 头部企业通过知识管理实现团队协作效率显著提升
- [hf] 开源社区发布新的推理优化框架，推理速度提升约 40%
- [external] 跨领域知识迁移可有效降低认知偏差
"""

    # ===== Day 7: Gödel 三层混合验证池 =====
    GODEL_VALIDATION_POOL: Dict[str, Any] = {
        "history_days": 7,
        "history_min": 10,
        "history_limit": 20,
        "adversarial_count": 5,
        "base_weight": 0.3,
        "history_weight": 0.4,
        "adversarial_weight": 0.3,
        "pass_threshold": 0.6,
    }

    @classmethod
    def get_path(cls, key: str) -> Path:
        return cls.DATA_ROOT / cls.PATHS[key]
    
    @classmethod
    def get_db_path(cls) -> Path:
        override = os.getenv("CRYSTAL_TREE_DB_PATH")
        if override:
            return Path(override).absolute()
        if cls.DATA_ROOT != PROJECT_ROOT:
            return cls.DATA_ROOT / "chat_sessions.db"
        return PROJECT_ROOT / "chat_sessions.db"

    @classmethod
    def get_api_key(cls) -> str:
        return os.getenv("DEEPSEEK_API_KEY", "")

    @staticmethod
    def _determine_data_root() -> Path:
        """智能检测数据根目录：环境变量 → 晶体树文件夹 → 当前目录"""
        env_root = os.getenv("CRYSTAL_TREE_DATA_ROOT")
        if env_root:
            return Path(env_root).absolute()
        candidate = PROJECT_ROOT / "晶体树文件夹"
        if candidate.exists() and candidate.is_dir():
            return candidate
        return PROJECT_ROOT


# ===== 关键修正：在类外部重新设置 DATA_ROOT =====
Config.DATA_ROOT = Config._determine_data_root()

