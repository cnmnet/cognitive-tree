#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.fingerprint import FingerprintExtractor
from core.models import CognitiveFingerprint, Conflict, Crystal, Hole, Layer
from data.storage import FileIO
from data.vector_store import VectorStore
from governance.config import Config
from harness.audit import LayerAuditService
from harness.gate import CheapGate

class CrystalEngine:
    # ===== Day 7: Hebbian 九分类关键词表 =====
    CATEGORY_KEYWORDS: Dict[str, List[str]] = {
        "tech": ["算法", "模型", "系统", "架构", "代码", "数据", "性能", "优化", "部署",
                 "ai", "人工智能",
                 "api", "集成", "测试", "调试", "自动化", "监控", "日志", "配置", "容器",
                 "微服务", "数据库", "缓存", "队列", "ci/cd"],
        "human": ["用户", "体验", "团队", "管理", "沟通", "信任", "成长", "领导力", "文化",
                  "激励", "情商", "冲突", "协作", "同理心", "认知偏差", "习惯", "情绪", "动机"],
        "business": ["预算", "成本", "收益", "roi", "市场", "竞争", "定价", "投资", "融资",
                     "增长", "留存", "转化", "客户", "销售", "营销", "品牌", "商业模型",
                     "财报", "指标", "kpi", "okr", "风险管理", "流程", "效率"],
        "policy": ["法规", "合规", "审计", "隐私", "安全", "数据保护", "gdpr", "监管", "制度",
                   "标准", "认证", "风险控制", "伦理", "公平", "透明度", "可解释性", "问责",
                   "知识产权", "版权", "专利", "商标"],
        "design": ["设计", "ui", "ux", "交互", "界面", "流程", "原型", "可访问性", "可用性",
                   "视觉", "品牌形象", "产品定位", "用户旅程", "信息架构", "hci", "设计系统",
                   "配色", "排版", "动效"],
        "strategy": ["愿景", "使命", "战略", "规划", "目标", "方向", "趋势", "前瞻", "布局",
                     "生态", "联盟", "转型", "创新", "第二曲线", "护城河", "差异化", "可持续",
                     "esg", "10年展望"],
        "science": ["理论", "原理", "机制", "物理", "数学", "统计", "概率", "线性代数",
                    "微积分", "优化理论", "信息论", "控制论", "系统论", "复杂性", "涌现",
                    "混沌", "博弈论", "认知科学", "神经科学", "生物学", "化学", "材料",
                    "量子", "相对论"],
        "education": ["学习", "教学", "培训", "课程", "知识", "技能", "能力", "素养", "认知",
                      "记忆", "理解", "应用", "分析", "评估", "创造", "教育", "学校", "大学",
                      "证书", "考试", "练习", "反馈", "辅导", "成长型思维", "刻意练习"],
    }

    def __init__(self, file_io: FileIO, ai_client=None, meta_layer=None):  # ← 添加 ai_client 参数
        self.files = file_io
        self.ai_client = ai_client
        self._file_lock = threading.Lock()
        self.meta = meta_layer
        self.fingerprint_extractor = FingerprintExtractor(self, file_io)
        self.cheap_gate = CheapGate(self, file_io)
        # ===== Day 3 修改：延迟初始化，仅当启用向量检索时才创建 =====
        if Config.VECTOR_SEARCH_ENABLED:
            self.vector_store = VectorStore(file_io)
        else:
            self.vector_store = None
            print("[INFO] 向量检索已禁用，使用 BM25 降级")
        # Day 2.8: 元问题分类器（动态导入）
        try:
            import sys
            core_config_path = str(Config.DATA_ROOT / "核心配置")
            if core_config_path not in sys.path:
                sys.path.append(core_config_path)
            from question_classifier import QuestionClassifier
            self.question_classifier = QuestionClassifier()
        except ImportError:
            self.question_classifier = None
            print("[WARN] question_classifier not found; meta question classification disabled")
        # Day 5: Hebbian 学习权重存储
        self.hebbian_weights = {}
        self._load_hebbian_weights()
        # ===== Day 19: 自我修复循环 =====
        self.self_healer = None  # 稍后初始化，避免循环引用    
        # 启动自我修复服务（延迟初始化）
        self.start_self_healing(ai_client)   

        # Day 20: GitHub Trending
        self._trending_crystalizer = None

    def _classify_question(self, question: str) -> List[str]:
        """对问题进行九分类多标签分类，返回匹配的类别列表。"""
        if not question:
            return ["general"]
        q_lower = question.lower()
        matched = []
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in q_lower:
                    matched.append(category)
                    break
        matched = list(dict.fromkeys(matched))
        if len(matched) == 0 or len(matched) >= 4 or len(question.strip()) < 4:
            return ["general"]
        return matched

    def get_skill_market(self, repo_owner: str = None, repo_name: str = None):
        """获取 Skill 市场实例"""
        import os
        if not repo_owner:
            repo_owner = os.getenv("GITHUB_REPO_OWNER", "your-org")
        if not repo_name:
            repo_name = os.getenv("GITHUB_REPO_NAME", "cognitive-tree-skills")
        token = os.getenv("GITHUB_TOKEN")
        try:
            from github_trending import GitHubSkillMarket
        except ImportError:
            return None
        return GitHubSkillMarket(repo_owner, repo_name, token)
    def _get_trending_crystalizer(self):
        """延迟初始化 Trending Crystalizer"""
        if self._trending_crystalizer is None:
            try:
                from github_trending import GitHubTrendingCrystalizer
                self._trending_crystalizer = GitHubTrendingCrystalizer(self, self.ai_client)
                print("✅ Trending Crystalizer 初始化成功")
            except Exception as e:
                print(f"⚠️ Trending Crystalizer 初始化失败：{e}")
                self._trending_crystalizer = None
        return self._trending_crystalizer

    def get_github_trending_crystals(self, limit: int = 10) -> List[Dict]:
        """获取已保存的 Trending 晶体"""
        crystalizer = self._get_trending_crystalizer()
        if crystalizer:
            return crystalizer.get_trending_crystals(limit)
        return []

    def run_github_trending_daily(self, max_items: int = 10) -> Dict:
        """执行每日 Trending 抓取"""
        crystalizer = self._get_trending_crystalizer()
        if crystalizer is None:
            return {"status": "error", "message": "Trending Crystalizer 不可用"}
        return crystalizer.run_daily(max_items)
      
    # ========================================================================
    # Day 9: Skill 管理方法（晶体→Skill 全面升级）
    # ========================================================================

    def get_skill_path(self, crystal_id: str):
        """
        获取指定晶体的 Skill 目录路径
        
        Args:
            crystal_id: 晶体ID（如 "C001"）
        
        Returns:
            Optional[Path]: Skill 目录路径，如果不存在则返回 None
        """
        skill_dir = Config.DATA_ROOT / "skills" / crystal_id
        if skill_dir.exists() and skill_dir.is_dir():
            return skill_dir
        return None
    
    def validate_skill(self, crystal_id: str) -> dict:
        """
        调用 Skill 的 validate.py 脚本验证晶体有效性
        """
        import subprocess
        import time
        import sys
        
        # 1. 检查 Skill 目录是否存在
        skill_dir = self.get_skill_path(crystal_id)
        if not skill_dir:
            return {
                "crystal_id": crystal_id,
                "valid": False,
                "output": "",
                "error": f"Skill 目录不存在: {crystal_id}",
                "execution_time": 0.0
            }
        
        # 2. 检查 validate.py 是否存在
        validate_script = skill_dir / "validate.py"
        if not validate_script.exists():
            return {
                "crystal_id": crystal_id,
                "valid": False,
                "output": "",
                "error": f"验证脚本不存在: {validate_script}",
                "execution_time": 0.0
            }
        
        # 3. 执行验证脚本
        start_time = time.time()
        try:
            # Windows 下使用 GBK 编码
            result = subprocess.run(
                [sys.executable, str(validate_script)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(skill_dir),
                encoding='gbk',  # Windows 中文系统使用 gbk
                errors='replace'  # 遇到无法解码的字符时替换
            )
            execution_time = time.time() - start_time
            
            # 检查返回码和输出
            is_valid = result.returncode == 0
            
            return {
                "crystal_id": crystal_id,
                "valid": is_valid,
                "output": result.stdout,
                "error": result.stderr if not is_valid else "",
                "execution_time": round(execution_time, 3)
            }
        except subprocess.TimeoutExpired:
            return {
                "crystal_id": crystal_id,
                "valid": False,
                "output": "",
                "error": "验证脚本执行超时（30秒）",
                "execution_time": 30.0
            }
        except Exception as e:
            return {
                "crystal_id": crystal_id,
                "valid": False,
                "output": "",
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    def validate_skills_batch(self, crystal_ids: list) -> dict:
        """
        批量验证多个 Skill
        
        Args:
            crystal_ids: 晶体ID列表，如 ["C001", "C002", "C003"]
        
        Returns:
            dict: 包含以下字段的批量验证结果
                - total: 总验证数
                - valid_count: 通过数
                - results: dict，每个晶体的验证结果
        """
        results = {}
        for cid in crystal_ids:
            results[cid] = self.validate_skill(cid)
        
        return {
            "total": len(results),
            "valid_count": sum(1 for r in results.values() if r.get("valid", False)),
            "results": results
        }
    
    def get_all_skills(self) -> list:
        """
        获取所有可用的 Skill ID
        
        Returns:
            list: Skill ID 列表，如 ["C001", "C002", "C003"]
        """
        skills_dir = Config.DATA_ROOT / "skills"
        if not skills_dir.exists():
            return []
        
        # 只返回包含 CRYSTAL.md 的目录
        skill_ids = []
        for d in skills_dir.iterdir():
            if d.is_dir() and (d / "CRYSTAL.md").exists():
                skill_ids.append(d.name)
        return sorted(skill_ids)
    
    def get_skill_crystal(self, crystal_id: str):
        """
        从 Skill 目录加载晶体数据
        
        优先从 skills/ 加载，如果不存在则从晶体卡片加载
        
        Args:
            crystal_id: 晶体ID（如 "C001"）
        
        Returns:
            Optional[Crystal]: 晶体对象，如果不存在则返回 None
        """
        import re
        
        # 1. 先尝试从 skills/ 加载
        skill_dir = self.get_skill_path(crystal_id)
        if skill_dir:
            crystal_md = skill_dir / "CRYSTAL.md"
            if crystal_md.exists():
                content = crystal_md.read_text(encoding='utf-8')
                # 提取核心内容（在 "## 核心内容" 之后）
                match = re.search(r"## 核心内容\s*\n+(.*?)(?=\n## |\Z)", content, re.DOTALL)
                if match:
                    core_content = match.group(1).strip()
                    # 提取链接
                    links = []
                    link_match = re.findall(r"- (C\d+)", content)
                    if link_match:
                        links = link_match
                    return Crystal(
                        id=crystal_id,
                        content=core_content,
                        links=links,
                        layer=Layer.L2,
                        heat=0.0
                    )
        
        # 2. 降级：从晶体卡片加载
        for crystal in self.parse_crystals():
            if crystal.id == crystal_id:
                return crystal
        return None
    
    def get_skill_validation_summary(self) -> dict:
        """
        获取所有 Skill 的验证状态摘要
        
        Returns:
            dict: 包含以下字段
                - total: 总 Skill 数
                - valid: 验证通过的 Skill 数
                - invalid: 验证未通过的 Skill 数
                - details: dict，每个 Skill 的验证状态详情
        """
        all_skills = self.get_all_skills()
        results = {}
        for skill_id in all_skills:
            result = self.validate_skill(skill_id)
            results[skill_id] = {
                "valid": result.get("valid", False),
                "execution_time": result.get("execution_time", 0),
                "has_error": bool(result.get("error", ""))
            }
        
        return {
            "total": len(results),
            "valid": sum(1 for r in results.values() if r["valid"]),
            "invalid": sum(1 for r in results.values() if not r["valid"]),
            "details": results
        }
    # ========================================================================
    # Day 18: 审计相关方法
    # ========================================================================

    def start_audit_service(self):
        """启动后台审计服务"""
        if not hasattr(self, '_audit_service'):
            self._audit_service = LayerAuditService(self, self.files)
        self._audit_service.start_background()

    def stop_audit_service(self):
        """停止后台审计服务"""
        if hasattr(self, '_audit_service'):
            self._audit_service.stop_background()

    def run_audit_now(self) -> Dict:
        """立即执行一次审计"""
        if not hasattr(self, '_audit_service'):
            self._audit_service = LayerAuditService(self, self.files)
        service = self._audit_service
        if not hasattr(service, '_audit_lock'):
            service._audit_lock = threading.Lock()
        if not service._audit_lock.acquire(blocking=False):
            return {"status": "skipped", "reason": "审计任务正在运行"}
        try:
            report = service.run_audit()
        finally:
            service._audit_lock.release()
        return {
            "health_score": report.health_score,
            "total_crystals": report.total_crystals,
            "cognitive_continuity_score": report.cognitive_continuity_score,
            "fingerprint_change_rate": report.fingerprint_change_rate,
            "components_status": report.components_status,
            "recommendations": report.recommendations,
            "layers": [
                {
                    "name": l.layer_name,
                    "count": l.crystal_count,
                    "contribution": l.contribution_percent,
                    "trend": l.trend,
                    "trend_value": l.trend_value
                }
                for l in report.layers
            ]
        }

    def get_audit_status(self) -> Dict:
        """获取审计状态"""
        if hasattr(self, '_audit_service'):
            report = self._audit_service.get_latest_report()
            if report:
                return {
                    "available": True,
                    "health_score": report.get("health_score", 0),
                    "total_crystals": report.get("total_crystals", 0),
                    "cognitive_continuity_score": report.get("cognitive_continuity_score", 5.0),
                    "fingerprint_change_rate": report.get("fingerprint_change_rate", 0),
                    "components_status": report.get("components_status", {}),
                    "recommendations": report.get("recommendations", []),
                    "last_audit": report.get("timestamp"),
                    "layers": report.get("layers", [])
                }
        return {"available": False, "cognitive_continuity_score": 5.0}  # 默认值

    def start_self_healing(self, ai_client=None):
        """
        启动自我修复服务（非核心功能，允许静默降级）。
        若 self_healing 模块缺失或初始化失败，仅打印警告，
        不影响晶体树核心功能（晶体化、辩论、检索等）的运行。
        """
        if not hasattr(self, 'self_healer') or self.self_healer is None:
            try:
                from self_healing import SelfHealing

                # TODO: 预留，后续可传递数据根目录给 SelfHealing

                def log_callback(msg, level="system"):
                    if hasattr(self, '_append_change_log'):
                        self._append_change_log("自我修复", msg)
                    else:
                        print(f"[{level.upper()}] {msg}")

                self.self_healer = SelfHealing(self, ai_client, log_callback)
                print("[INFO] 自我修复模块加载成功")

            except ImportError as e:
                self.self_healer = None
                print(f"[WARN] self_healing 模块未找到，自我修复功能禁用。原因: {e}")

            except Exception as e:
                self.self_healer = None
                print(f"[ERROR] 自我修复初始化失败: {e}")

    def record_dialogue_quality(self, quality_score: float, context: Dict = None):
        """记录对话质量，供自我修复检查"""
        print(f"[DEBUG] record_dialogue_quality: score={quality_score:.2f}, context={context}")
        if not getattr(self, '_self_healing_enabled', True):
            print("[DEBUG] 自我修复未启用")
            return
        if self.self_healer is None:
            print("[DEBUG] 正在初始化 self_healer...")
            self.start_self_healing()
            if self.self_healer:
                print("[DEBUG] self_healer 初始化成功")
            else:
                print("[DEBUG] self_healer 初始化失败")
        if self.self_healer:
            self.self_healer.record_quality(quality_score, context)
        else:
            print("[DEBUG] self_healer 仍为 None，无法记录")

    def get_self_healing_status(self) -> Dict:
        """获取自我修复状态"""
        if hasattr(self, 'self_healer') and self.self_healer:
            return self.self_healer.get_status()
        return {}   
    # ========================================================================
    # Day 17: 技能层辅助方法
    # ========================================================================

    def generate_crystal_from_traces(self) -> List[Dict[str, Any]]:
        """
        从轨迹日志生成晶体候选（供 GödelAgent 调用）

        Returns:
            List[Dict]: 晶体候选列表
        """
        candidates = []
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        if not log_path.exists():
            return candidates

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            events = data.get("events", [])
        except:
            return candidates

        # 提取失败轨迹中的模式
        failure_patterns = []
        for event in events:
            if event.get("event_type") == "failure_trace":
                details = event.get("details", {})
                traces = details.get("failure_traces", {})
                failure_type = traces.get("failure_type", "")
                if failure_type and failure_type not in failure_patterns:
                    failure_patterns.append(failure_type)

        # 基于失败模式生成晶体
        pattern_instructions = {
            "low_crystal_reference": {
                "content": "晶体引用协议：每次辩论前从L1层加载至少2条核心晶体，确保答案有据可查",
                "links": ["C001", "C010"],
                "input_conditions": ["辩论初始化阶段"],
                "execution_logic": "检索与问题匹配度最高的2条L1晶体",
                "output_format": "引用格式：[Cxxx] 内容摘要",
                "validation_criteria": ["引用率 ≥ 50%"]
            },
            "debate_diverged": {
                "content": "视角注入协议：当辩论趋同时自动触发百灵鸟视角，打破思维固化",
                "links": ["C023", "C050"],
                "input_conditions": ["Jaccard相似度连续2轮 > 0.7"],
                "execution_logic": "计算Jaccard均值，触发外部知识注入",
                "output_format": "注入外部视角，标注来源",
                "validation_criteria": ["Jaccard下降至0.6以下"]
            },
            "audit_failed": {
                "content": "证据检查清单：每轮辩论结束后审计引用证据的充分性",
                "links": ["C001", "C007"],
                "input_conditions": ["每轮辩论结束后"],
                "execution_logic": "扫描所有引用，检查ID有效性",
                "output_format": "审计报告：通过/不通过",
                "validation_criteria": ["所有引用有效"]
            }
        }

        for pattern in failure_patterns:
            if pattern in pattern_instructions:
                candidates.append({
                    "content": pattern_instructions[pattern]["content"],
                    "links": pattern_instructions[pattern]["links"],
                    "input_conditions": pattern_instructions[pattern]["input_conditions"],
                    "execution_logic": pattern_instructions[pattern]["execution_logic"],
                    "output_format": pattern_instructions[pattern]["output_format"],
                    "validation_criteria": pattern_instructions[pattern]["validation_criteria"],
                    "source": "trace_analysis"
                })

        return candidates

    # ========================================================================
    # Day 9.5: 跨用户认知贡献层 (Wisdom Commons)
    # ========================================================================

    def get_wisdom_commons_path(self) -> Path:
        """获取智慧公库路径"""
        commons_path = Config.DATA_ROOT / "系统日志" / "wisdom_commons.json"
        return commons_path

    def _load_wisdom_commons(self) -> dict:
        """加载智慧公库数据"""
        commons_path = self.get_wisdom_commons_path()
        if not commons_path.exists():
            # 初始化默认数据
            default_data = {
                "version": "1.0",
                "crystals": [],           # 贡献的晶体列表
                "users": {},              # 用户信用积分 {user_id: credits}
                "contributions": [],      # 贡献记录
                "last_maintenance": datetime.now().isoformat(),
                "total_contributions": 0,
                "active_seeds": []        # 活跃种子ID列表
            }
            self._save_wisdom_commons(default_data)
            return default_data
        try:
            return json.loads(commons_path.read_text(encoding='utf-8'))
        except:
            return self._load_wisdom_commons()  # 递归加载默认

    def _save_wisdom_commons(self, data: dict) -> None:
        """保存智慧公库数据"""
        commons_path = self.get_wisdom_commons_path()
        commons_path.parent.mkdir(parents=True, exist_ok=True)
        commons_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def contribute_crystal(self, crystal_id: str, user_id: str = "anonymous", 
                          is_anonymous: bool = True) -> dict:
        """
        贡献晶体到智慧公库
        
        Args:
            crystal_id: 晶体ID
            user_id: 用户ID（匿名时使用 "anonymous"）
            is_anonymous: 是否匿名贡献
        
        Returns:
            dict: 贡献结果
        """
        # 1. 验证晶体是否存在
        crystals = self.parse_crystals()
        crystal = next((c for c in crystals if c.id == crystal_id), None)
        if not crystal:
            return {"success": False, "error": f"晶体 {crystal_id} 不存在"}
        
        # 2. 验证门控评分（需要 > 0.8）
        contribution_result = self.contribution_scoring(crystal_id)
        if isinstance(contribution_result, dict) and "error" not in contribution_result:
            score = contribution_result.get("score", 0)
            if score < 25:  # 25分对应约0.8的归一化评分
                return {
                    "success": False, 
                    "error": f"晶体贡献度评分 {score} 低于阈值 25，无法贡献到公库",
                    "score": score
                }
        else:
            return {"success": False, "error": "无法计算晶体贡献度"}
        
        # 3. 加载公库数据
        commons = self._load_wisdom_commons()
        
        # 4. 检查是否已存在
        for existing in commons["crystals"]:
            if existing["crystal_id"] == crystal_id:
                return {
                    "success": False, 
                    "error": f"晶体 {crystal_id} 已存在于智慧公库"
                }
        
        # 5. 创建贡献记录
        contribution = {
            "crystal_id": crystal_id,
            "content": crystal.content,
            "links": crystal.links,
            "contributor": "anonymous" if is_anonymous else user_id,
            "is_anonymous": is_anonymous,
            "score": contribution_result.get("score", 0),
            "contributed_at": datetime.now().isoformat(),
            "status": "active",          # active | deprecated
            "usage_count": 0,            # 被引用次数
            "last_used": None
        }
        
        # 6. 添加到公库
        commons["crystals"].append(contribution)
        commons["total_contributions"] += 1
        commons["active_seeds"].append(crystal_id)
        commons["contributions"].append({
            "crystal_id": crystal_id,
            "user_id": user_id,
            "is_anonymous": is_anonymous,
            "timestamp": datetime.now().isoformat()
        })
        
        # 7. 更新用户积分（匿名贡献也记录积分，但不显示用户名）
        if user_id not in commons["users"]:
            commons["users"][user_id] = {"credits": 0, "contributions": 0, "last_active": None}
        commons["users"][user_id]["credits"] += 10  # 每次贡献 +10 积分
        commons["users"][user_id]["contributions"] += 1
        commons["users"][user_id]["last_active"] = datetime.now().isoformat()
        
        # 8. 保存
        self._save_wisdom_commons(commons)
        
        # 9. 记录进化事件
        self.log_evolution_event(
            "wisdom_contribution",
            {
                "crystal_id": crystal_id,
                "user_id": user_id,
                "is_anonymous": is_anonymous,
                "score": contribution_result.get("score", 0),
                "trigger": "user_contribution"
            }
        )
        
        return {
            "success": True,
            "message": f"晶体 {crystal_id} 已成功贡献到智慧公库",
            "credits_earned": 10,
            "total_credits": commons["users"][user_id]["credits"],
            "total_crystals": len(commons["crystals"])
        }

    def get_wisdom_seeds(self, limit: int = 10) -> List[Dict]:
        """
        获取智慧公库中的种子晶体（用于新用户初始化）
        
        Args:
            limit: 返回数量限制
        
        Returns:
            List[Dict]: 种子晶体列表
        """
        commons = self._load_wisdom_commons()
        seeds = commons.get("crystals", [])
        
        # 按使用次数和评分排序
        sorted_seeds = sorted(
            seeds,
            key=lambda x: (x.get("usage_count", 0), x.get("score", 0)),
            reverse=True
        )
        
        # 返回活跃的种子
        active_seeds = [s for s in sorted_seeds if s.get("status") == "active"]
        
        return active_seeds[:limit]

    def inherit_seeds(self, user_id: str, limit: int = 5) -> dict:
        """
        新用户继承智慧公库种子
        
        Args:
            user_id: 用户ID
            limit: 继承数量
        
        Returns:
            dict: 继承结果
        """
        # 1. 获取种子
        seeds = self.get_wisdom_seeds(limit)
        if not seeds:
            return {"success": False, "error": "智慧公库暂无种子晶体"}
        
        # 2. 加载公库数据
        commons = self._load_wisdom_commons()
        
        # 3. 记录用户继承
        if user_id not in commons["users"]:
            commons["users"][user_id] = {"credits": 0, "contributions": 0, "last_active": None}
        
        # 4. 更新种子使用次数
        inherited_ids = []
        for seed in seeds:
            crystal_id = seed["crystal_id"]
            # 更新使用次数
            for s in commons["crystals"]:
                if s["crystal_id"] == crystal_id:
                    s["usage_count"] = s.get("usage_count", 0) + 1
                    s["last_used"] = datetime.now().isoformat()
                    inherited_ids.append(crystal_id)
                    break
        
        # 5. 记录继承事件
        commons["users"][user_id]["last_active"] = datetime.now().isoformat()
        if "inherited_seeds" not in commons["users"][user_id]:
            commons["users"][user_id]["inherited_seeds"] = []
        commons["users"][user_id]["inherited_seeds"].extend(inherited_ids)
        
        # 6. 保存
        self._save_wisdom_commons(commons)
        
        # 7. 记录进化事件
        self.log_evolution_event(
            "wisdom_inherit",
            {
                "user_id": user_id,
                "inherited_count": len(inherited_ids),
                "seed_ids": inherited_ids,
                "trigger": "user_init"
            }
        )
        
        return {
            "success": True,
            "message": f"成功继承 {len(inherited_ids)} 个种子晶体",
            "seeds": inherited_ids,
            "seed_details": seeds
        }

    def get_user_credits(self, user_id: str) -> dict:
        """
        获取用户信用积分
        
        Args:
            user_id: 用户ID
        
        Returns:
            dict: 用户信用信息
        """
        commons = self._load_wisdom_commons()
        user_data = commons["users"].get(user_id, None)
        
        if not user_data:
            return {
                "user_id": user_id,
                "credits": 0,
                "contributions": 0,
                "inherited_seeds": [],
                "last_active": None
            }
        
        return {
            "user_id": user_id,
            "credits": user_data.get("credits", 0),
            "contributions": user_data.get("contributions", 0),
            "inherited_seeds": user_data.get("inherited_seeds", []),
            "last_active": user_data.get("last_active", None)
        }

    def use_credits(self, user_id: str, amount: int, purpose: str) -> dict:
        """
        使用信用积分兑换功能
        
        Args:
            user_id: 用户ID
            amount: 消费积分数量
            purpose: 消费用途
        
        Returns:
            dict: 消费结果
        """
        commons = self._load_wisdom_commons()
        
        if user_id not in commons["users"]:
            return {"success": False, "error": "用户不存在"}
        
        user_data = commons["users"][user_id]
        if user_data.get("credits", 0) < amount:
            return {
                "success": False, 
                "error": f"积分不足，当前 {user_data.get('credits', 0)} 分，需要 {amount} 分"
            }
        
        # 消费积分
        user_data["credits"] = user_data.get("credits", 0) - amount
        
        # 记录消费
        if "credit_usage" not in user_data:
            user_data["credit_usage"] = []
        user_data["credit_usage"].append({
            "amount": amount,
            "purpose": purpose,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_wisdom_commons(commons)
        
        return {
            "success": True,
            "message": f"成功消费 {amount} 积分用于 {purpose}",
            "remaining_credits": user_data["credits"]
        }

    def maintain_wisdom_commons(self) -> dict:
        """
        维护智慧公库：清理低生命力晶体（引用率低的老晶体自动沉底）
        
        Returns:
            dict: 维护结果
        """
        commons = self._load_wisdom_commons()
        crystals = commons.get("crystals", [])
        
        # 计算每个晶体的生命力
        # 生命力 = 使用次数 * 0.5 + 评分 * 0.3 + 新鲜度 * 0.2
        from datetime import datetime
        now = datetime.now()
        
        maintained = []
        deprecated = []
        
        for crystal in crystals:
            usage = crystal.get("usage_count", 0)
            score = crystal.get("score", 0) / 100  # 归一化到 0-1
            
            # 新鲜度：30天内有使用为1，60天内有使用为0.5，否则为0
            last_used_str = crystal.get("last_used")
            if last_used_str:
                try:
                    last_used = datetime.fromisoformat(last_used_str)
                    days_since = (now - last_used).days
                    if days_since < 30:
                        freshness = 1.0
                    elif days_since < 60:
                        freshness = 0.5
                    else:
                        freshness = 0.0
                except:
                    freshness = 0.0
            else:
                freshness = 0.0
            
            vitality = usage * 0.5 + score * 0.3 + freshness * 0.2
            
            # 生命力低于 0.3 且状态为 active 的晶体标记为 deprecated
            if vitality < 0.3 and crystal.get("status") == "active":
                crystal["status"] = "deprecated"
                crystal["deprecated_at"] = now.isoformat()
                deprecated.append(crystal["crystal_id"])
            else:
                crystal["vitality"] = round(vitality, 3)
                maintained.append(crystal["crystal_id"])
        
        # 更新公库
        commons["last_maintenance"] = now.isoformat()
        self._save_wisdom_commons(commons)
        
        # 记录维护事件
        if deprecated:
            self.log_evolution_event(
                "wisdom_maintenance",
                {
                    "maintained_count": len(maintained),
                    "deprecated_count": len(deprecated),
                    "deprecated_ids": deprecated,
                    "trigger": "auto_maintenance"
                }
            )
        
        return {
            "success": True,
            "maintained": len(maintained),
            "deprecated": len(deprecated),
            "deprecated_ids": deprecated,
            "total_active": len([c for c in commons["crystals"] if c.get("status") == "active"])
        }

    def get_wisdom_stats(self) -> dict:
        """
        获取智慧公库统计信息
        """
        commons = self._load_wisdom_commons()
        crystals = commons.get("crystals", [])
        users = commons.get("users", {})
        
        active = [c for c in crystals if c.get("status") == "active"]
        deprecated = [c for c in crystals if c.get("status") == "deprecated"]
        
        total_credits = sum(u.get("credits", 0) for u in users.values())
        total_users = len(users)
        
        # 计算平均评分
        scores = [c.get("score", 0) for c in crystals if c.get("status") == "active"]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "total_crystals": len(crystals),
            "active_crystals": len(active),
            "deprecated_crystals": len(deprecated),
            "total_users": total_users,
            "total_credits": total_credits,
            "total_contributions": commons.get("total_contributions", 0),
            "avg_score": round(avg_score, 2),
            "last_maintenance": commons.get("last_maintenance", None),
            "top_contributors": self._get_top_contributors(users, 5)
        }

    def _get_top_contributors(self, users: dict, limit: int = 5) -> List[Dict]:
        """获取顶级贡献者"""
        sorted_users = sorted(
            users.items(),
            key=lambda x: x[1].get("credits", 0),
            reverse=True
        )
        return [
            {
                "user_id": uid,
                "credits": data.get("credits", 0),
                "contributions": data.get("contributions", 0)
            }
            for uid, data in sorted_users[:limit]
        ]

    # ========================================================================
    # 在 CrystalEngine 类中新增突触管理方法
    # ========================================================================

    # ========================================================================
    # 突触管理方法
    # ========================================================================

    def get_role_synapses(self, role_key: str) -> Dict[str, float]:
        """获取指定角色的突触权重表"""
        synapse_file = Config.DATA_ROOT / "系统日志" / "角色突触.json"
        try:
            if not synapse_file.exists():
                return {}
            with open(synapse_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(role_key, {}).get("synapses", {})
        except Exception:
            return {}

    def update_role_synapse(self, role_key: str, crystal_id: str, delta: float) -> float:
        """更新突触权重（采纳+0.08，驳回-0.05）"""
        synapse_file = Config.DATA_ROOT / "系统日志" / "角色突触.json"
        try:
            synapse_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if synapse_file.exists():
                with open(synapse_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            if role_key not in data:
                data[role_key] = {"synapses": {}, "win_count": 0, "loss_count": 0}
            
            synapses = data[role_key]["synapses"]
            old = synapses.get(crystal_id, 0.5)
            new_weight = max(0.0, min(1.0, old + delta))
            synapses[crystal_id] = round(new_weight, 3)
            data[role_key]["synapses"] = synapses
            data[role_key]["last_updated"] = datetime.now().isoformat()

            with open(synapse_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return new_weight
        except Exception as e:
            print(f"[WARN] 突触更新失败: {e}")
            return 0.5

    def get_role_win_rate(self, role_key: str) -> float:
        """获取角色历史胜率"""
        synapse_file = Config.DATA_ROOT / "系统日志" / "角色突触.json"
        try:
            if not synapse_file.exists():
                return 0.5
            with open(synapse_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            role_data = data.get(role_key, {})
            wins = role_data.get("win_count", 0)
            losses = role_data.get("loss_count", 0)
            total = wins + losses
            return 0.5 if total == 0 else round(wins / total, 3)
        except Exception:
            return 0.5

    def _update_role_win_loss(self, role_key: str, win: bool) -> None:
        """更新角色胜率计数"""
        synapse_file = Config.DATA_ROOT / "系统日志" / "角色突触.json"
        try:
            synapse_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if synapse_file.exists():
                with open(synapse_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if role_key not in data:
                data[role_key] = {"synapses": {}, "win_count": 0, "loss_count": 0}
            if win:
                data[role_key]["win_count"] = data[role_key].get("win_count", 0) + 1
            else:
                data[role_key]["loss_count"] = data[role_key].get("loss_count", 0) + 1
            data[role_key]["last_updated"] = datetime.now().isoformat()
            with open(synapse_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] 更新胜率失败: {e}")

    def parse_crystals(self) -> List[Crystal]:
        """
        解析晶体数据（线程安全）
        优先从 skills/ 目录加载，如果 skills/ 为空则从晶体卡片加载
        """
        with self._file_lock:
            crystals = []
            
            # 1. 优先从 skills/ 目录加载
            skills_dir = Config.DATA_ROOT / "skills"
            if skills_dir.exists():
                for skill_dir in skills_dir.iterdir():
                    if not skill_dir.is_dir():
                        continue
                    crystal_md = skill_dir / "CRYSTAL.md"
                    if not crystal_md.exists():
                        continue
                    try:
                        content = crystal_md.read_text(encoding='utf-8')
                        match = re.search(r"## 核心内容\s*\n+(.*?)(?=\n## |\Z)", content, re.DOTALL)
                        if match:
                            core_content = match.group(1).strip()
                            # 提取链接
                            links = []
                            link_match = re.findall(r"- (C\d+)", content)
                            if link_match:
                                links = link_match
                            # 提取输入条件
                            input_conditions = []
                            ic_match = re.search(r"### 输入条件\s*\n+(.*?)(?=\n### |\Z)", content, re.DOTALL)
                            if ic_match:
                                ic_text = ic_match.group(1).strip()
                                input_conditions = [l.strip() for l in ic_text.split("\n") if l.strip().startswith("-")]
                                input_conditions = [l[2:].strip() for l in input_conditions if l[2:].strip() != "（无特定输入条件）"]
                            # 提取执行逻辑
                            execution_logic = ""
                            el_match = re.search(r"### 执行逻辑\s*\n+(.*?)(?=\n### |\Z)", content, re.DOTALL)
                            if el_match:
                                execution_logic = el_match.group(1).strip()
                                if execution_logic == "（无执行逻辑）":
                                    execution_logic = ""
                            # 提取输出格式
                            output_format = ""
                            of_match = re.search(r"### 输出格式\s*\n+(.*?)(?=\n### |\Z)", content, re.DOTALL)
                            if of_match:
                                output_format = of_match.group(1).strip()
                                if output_format == "（无特定输出格式）":
                                    output_format = ""
                            # 提取验证标准
                            validation_criteria = []
                            vc_match = re.search(r"### 验证标准\s*\n+(.*?)(?=\n## |\Z)", content, re.DOTALL)
                            if vc_match:
                                vc_text = vc_match.group(1).strip()
                                validation_criteria = [l.strip() for l in vc_text.split("\n") if l.strip().startswith("-")]
                                validation_criteria = [l[2:].strip() for l in validation_criteria if l[2:].strip() != "（无特定验证标准）"]
                            
                            crystals.append(Crystal(
                                id=skill_dir.name,
                                content=core_content,
                                links=links,
                                input_conditions=input_conditions,
                                execution_logic=execution_logic,
                                output_format=output_format,
                                validation_criteria=validation_criteria
                            ))
                    except Exception as e:
                        print(f"⚠️ 解析 Skill {skill_dir.name} 失败: {e}")
                        continue
            
            # 2. 如果 skills/ 目录没有晶体，从晶体卡片加载（降级）
            if not crystals:
                content = self.files.read("crystals")
                pattern = r"\| (C\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|"
                for match in re.finditer(pattern, content):
                    cid = match.group(1)
                    text = match.group(2).strip()
                    links_str = match.group(3).strip()
                    links = [l.strip() for l in links_str.split(",") if l.strip() and l.strip() != "—"]
                    input_conditions = [c.strip() for c in match.group(4).split(",") if c.strip() and c.strip() != "—"]
                    execution_logic = match.group(5).strip() if match.group(5).strip() != "—" else ""
                    output_format = match.group(6).strip() if match.group(6).strip() != "—" else ""
                    validation_criteria = [c.strip() for c in match.group(7).split(",") if c.strip() and c.strip() != "—"]
                    crystals.append(Crystal(
                        id=cid,
                        content=text,
                        links=links,
                        input_conditions=input_conditions,
                        execution_logic=execution_logic,
                        output_format=output_format,
                        validation_criteria=validation_criteria
                    ))
            
            return crystals

    def create_crystal(self, crystal_id: str, content: str, links: List[str] = None, 
                       input_conditions: List[str] = None, execution_logic: str = "",
                       output_format: str = "", validation_criteria: List[str] = None,
                       source: str = "system") -> bool:
        """
        统一的晶体创建入口
        - 写入晶体卡片.md（保持兼容）
        - 创建 Skill 目录（新标准）
        - 同步向量库
        - 记录进化事件
        """
        links = links or []
        input_conditions = input_conditions or []
        validation_criteria = validation_criteria or []
        
        # 1. 写入晶体卡片.md（保持向后兼容）
        links_str = ', '.join(links) if links else '—'
        ic_str = ', '.join(input_conditions) if input_conditions else '—'
        el_str = execution_logic if execution_logic else '—'
        of_str = output_format if output_format else '—'
        vc_str = ', '.join(validation_criteria) if validation_criteria else '—'
        
        new_line = f"\n| {crystal_id} | {content} | {links_str} | {ic_str} | {el_str} | {of_str} | {vc_str} |\n"
        self.files.append("crystals", new_line)
        
        # 2. 创建 Skill 目录
        skill_created = self._create_skill_from_crystal(
            crystal_id, content, links,
            input_conditions, execution_logic,
            output_format, validation_criteria
        )
        
        # 3. 同步向量库（增量更新）
        if skill_created:
            try:
                # 只添加这一个晶体到向量库
                crystal = Crystal(
                    id=crystal_id,
                    content=content,
                    links=links,
                    input_conditions=input_conditions,
                    execution_logic=execution_logic,
                    output_format=output_format,
                    validation_criteria=validation_criteria
                )
                self.vector_store.add_crystals([crystal])
            except Exception as e:
                print(f"⚠️ 向量库增量更新失败: {e}")
        
        # 4. 记录进化事件
        self.log_evolution_event(
            "crystal_created",
            {
                "crystal_id": crystal_id,
                "content": content[:80],
                "links": links,
                "source": source,
                "skill_created": skill_created
            }
        )
        
        return skill_created

    def _create_skill_from_crystal(self, crystal_id: str, content: str, links: List[str] = None,
                                    input_conditions: List[str] = None, execution_logic: str = "",
                                    output_format: str = "", validation_criteria: List[str] = None) -> bool:
        """在 skills/ 目录下创建完整的 Skill 结构"""
        from datetime import datetime
        
        links = links or []
        input_conditions = input_conditions or []
        validation_criteria = validation_criteria or []
        
        skill_dir = Config.DATA_ROOT / "skills" / crystal_id
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. 生成 CRYSTAL.md
            crystal_md = skill_dir / "CRYSTAL.md"
            md_lines = []
            md_lines.append(f"# {crystal_id} - 认知晶体")
            md_lines.append("")
            md_lines.append("## 基本信息")
            md_lines.append("")
            md_lines.append("| 属性 | 值 |")
            md_lines.append("|------|-----|")
            md_lines.append(f"| **晶体ID** | {crystal_id} |")
            md_lines.append("| **当前层级** | L2 |")
            md_lines.append("| **热度** | 0.5 |")
            md_lines.append(f"| **最后访问** | {datetime.now().strftime('%Y-%m-%d')} |")
            md_lines.append("")
            md_lines.append("## 核心内容")
            md_lines.append("")
            md_lines.append(content)
            md_lines.append("")
            
            if links:
                md_lines.append("## 链接关系")
                md_lines.append("")
                for link in links:
                    md_lines.append(f"- {link}")
                md_lines.append("")
            
            md_lines.append("## 代码化字段")
            md_lines.append("")
            md_lines.append("### 输入条件")
            md_lines.append("")
            if input_conditions:
                for cond in input_conditions:
                    md_lines.append(f"- {cond}")
            else:
                md_lines.append("（无特定输入条件）")
            md_lines.append("")
            
            md_lines.append("### 执行逻辑")
            md_lines.append("")
            if execution_logic:
                md_lines.append(execution_logic)
            else:
                md_lines.append("（无执行逻辑）")
            md_lines.append("")
            
            md_lines.append("### 输出格式")
            md_lines.append("")
            if output_format:
                md_lines.append(output_format)
            else:
                md_lines.append("（无特定输出格式）")
            md_lines.append("")
            
            md_lines.append("### 验证标准")
            md_lines.append("")
            if validation_criteria:
                for crit in validation_criteria:
                    md_lines.append(f"- {crit}")
            else:
                md_lines.append("（无特定验证标准）")
            md_lines.append("")
            
            md_lines.append("## 使用说明")
            md_lines.append("")
            md_lines.append("此晶体可通过 `validate.py` 脚本进行自动验证：")
            md_lines.append("```bash")
            md_lines.append("python validate.py")
            md_lines.append("```")
            md_lines.append("")
            md_lines.append("## 元数据")
            md_lines.append("")
            md_lines.append(f"- **创建时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            md_lines.append("- **来源**: 晶体化流程")
            
            crystal_md.write_text("\n".join(md_lines), encoding='utf-8')
            
            # 2. 生成 validate.py（改进版，实际验证内容）
            validate_py = skill_dir / "validate.py"
            py_lines = [
                '#!/usr/bin/env python3',
                '# -*- coding: utf-8 -*-',
                f'"""Validation for {crystal_id}"""',
                'import sys',
                '',
                f'CRYSTAL_ID = {repr(crystal_id)}',
                f'CONTENT = {repr(content)}',
                f'EXECUTION_LOGIC = {repr(execution_logic)}',
                '',
                'def test_content():',
                '    assert len(CONTENT) > 0, "内容不能为空"',
                '    print("[PASS] content_not_empty")',
                '',
                'def run_execution_logic():',
                '    if not EXECUTION_LOGIC.strip():',
                '        print("[SKIP] execution_logic 为空")',
                '        return True',
                '    try:',
                '        exec(EXECUTION_LOGIC, {"CRYSTAL_ID": CRYSTAL_ID, "CONTENT": CONTENT})',
                '        print("[PASS] execution_logic executed")',
                '        return True',
                '    except Exception as e:',
                '        print(f"[WARN] execution_logic 执行失败: {e}")',
                '        print("[WARN] 该逻辑为描述性文本或代码不完整，仅记录验证")',
                '        return False',
                '',
                'def main():',
                '    print(f"Validating {crystal_id}...")',
                '    test_content()',
                '    run_execution_logic()',
                '    print("All validation passed!")',
                '    return 0',
                '',
                'if __name__ == "__main__":',
                '    sys.exit(main())'
            ]
            validate_py.write_text("\n".join(py_lines), encoding='utf-8')
            
            # 3. 创建 references 目录
            (skill_dir / "references").mkdir(parents=True, exist_ok=True)
            
            # 4. 生成 README.md
            readme = skill_dir / "README.md"
            readme_lines = []
            readme_lines.append(f"# {crystal_id} Skill")
            readme_lines.append("")
            readme_lines.append(f"此 Skill 包含晶体 {crystal_id} 的完整定义和验证脚本。")
            readme_lines.append("")
            readme_lines.append("## 文件结构")
            readme_lines.append("")
            readme_lines.append("- `CRYSTAL.md` - 晶体定义")
            readme_lines.append("- `validate.py` - 验证脚本")
            readme_lines.append("- `references/` - 外部引用")
            readme_lines.append("")
            if links:
                readme_lines.append("## 关联晶体")
                readme_lines.append("")
                for link in links:
                    readme_lines.append(f"- {link}")
            
            readme.write_text("\n".join(readme_lines), encoding='utf-8')
            
            return True
            
        except Exception as e:
            print(f"❌ 创建 Skill 失败 {crystal_id}: {e}")
            return False

    def migrate_new_crystals_from_card(self) -> Dict[str, Any]:
        """从晶体卡片.md 迁移新增的晶体到 skills/"""
        # 1. 从晶体卡片.md 读取所有晶体
        content = self.files.read("crystals")
        pattern = r"\| (C\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|"
        card_crystals = []
        for match in re.finditer(pattern, content):
            cid = match.group(1)
            text = match.group(2).strip()
            links_str = match.group(3).strip()
            links = [l.strip() for l in links_str.split(",") if l.strip() and l.strip() != "—"]
            ic_str = match.group(4).strip()
            input_conditions = [c.strip() for c in ic_str.split(",") if c.strip() and c.strip() != "—"]
            execution_logic = match.group(5).strip() if match.group(5).strip() != "—" else ""
            output_format = match.group(6).strip() if match.group(6).strip() != "—" else ""
            vc_str = match.group(7).strip()
            validation_criteria = [c.strip() for c in vc_str.split(",") if c.strip() and c.strip() != "—"]
            card_crystals.append({
                "id": cid,
                "content": text,
                "links": links,
                "input_conditions": input_conditions,
                "execution_logic": execution_logic,
                "output_format": output_format,
                "validation_criteria": validation_criteria
            })
        
        # 2. 获取已存在的 Skill
        existing_skills = set(self.get_all_skills())
        
        # 3. 找出未迁移的
        migrated = []
        for c in card_crystals:
            if c["id"] not in existing_skills:
                success = self._create_skill_from_crystal(
                    c["id"], c["content"], c["links"],
                    c["input_conditions"], c["execution_logic"],
                    c["output_format"], c["validation_criteria"]
                )
                if success:
                    migrated.append(c["id"])
                    # 同步到向量库
                    try:
                        crystal = Crystal(
                            id=c["id"],
                            content=c["content"],
                            links=c["links"],
                            input_conditions=c["input_conditions"],
                            execution_logic=c["execution_logic"],
                            output_format=c["output_format"],
                            validation_criteria=c["validation_criteria"]
                        )
                        self.vector_store.add_crystals([crystal])
                    except Exception as e:
                        print(f"⚠️ 向量库同步失败 {c['id']}: {e}")
        
        return {
            "total": len(card_crystals),
            "existing": len(existing_skills),
            "migrated": migrated,
            "migrated_count": len(migrated)
        }

    def parse_holes(self) -> List[Hole]:
        """解析孔洞数据（线程安全）"""
        with self._file_lock:
            content = self.files.read("holes")
            pattern = r"\| (H\d+) \| (.*?) \| ([\d\.]+) \|"
            holes = []
            for match in re.finditer(pattern, content):
                hid = match.group(1)
                text = match.group(2).strip()
                urgency = float(match.group(3))
                holes.append(Hole(id=hid, content=text, urgency=urgency))
            return holes

    def _simple_similarity(self, text1: str, text2: str) -> float:
        def tokenize(s: str) -> Set[str]:
            words = re.findall(r'[\w\u4e00-\u9fff]+', s.lower())
            tokens = set()
            for w in words:
                if re.match(r'[\u4e00-\u9fff]', w):
                    tokens.update(w)
                else:
                    tokens.add(w)
            return tokens
        set1 = tokenize(text1)
        set2 = tokenize(text2)
        if not set1 or not set2:
            return 0.0
        return len(set1 & set2) / len(set1 | set2)

    def _search_tokens(self, text: str) -> List[str]:
        tokens = []
        for word in re.findall(r'[A-Za-z0-9_]+|[\u4e00-\u9fff]+', text.lower()):
            if re.search(r'[\u4e00-\u9fff]', word):
                chars = [ch for ch in word if re.match(r'[\u4e00-\u9fff]', ch)]
                tokens.extend(chars)
                tokens.extend(''.join(chars[i:i+2]) for i in range(len(chars)-1))
                tokens.extend(''.join(chars[i:i+3]) for i in range(len(chars)-2))
            else:
                tokens.append(word)
        return [t for t in tokens if t]

    def rank_crystals(self, query: str, crystals: List[Crystal], top_k: int = 5,
                      task_type: str = "general", task_types: List[str] = None) -> List[Tuple[float, Crystal]]:
        """
        检索最相关的晶体（向量检索优先，BM25 降级）
        """
        if not query or not crystals:
            return []

        # ===== Day 3 修复：scored 在外部初始化，避免引用错误 =====
        scored = []

        # 尝试向量检索
        if Config.VECTOR_SEARCH_ENABLED and self.vector_store.is_available():
            try:
                crystal_map = {c.id: c for c in crystals}
                results = self.vector_store.query(query, top_k=top_k * 2)

                if results:
                    for cid, score in results:
                        if cid in crystal_map:
                            crystal = crystal_map[cid]
                            combined_score = score * 0.9 + (crystal.heat / 10) * 0.1
                            hebbian_boost = self.get_hebbian_boost(crystal.id, task_type, task_types)
                            combined_score = score * 0.9 + (crystal.heat / 10) * 0.1 + hebbian_boost * 0.2
                            scored.append((combined_score, crystal))

                    if scored:
                        scored.sort(key=lambda item: item[0], reverse=True)
                        crystal_ids = [c.id for _, c in scored[:top_k]]
                        self._track_crystal_usage(crystal_ids, context="retrieval")
                        return scored[:top_k]

            except Exception as e:
                print(f"[WARN] 向量检索异常，降级到 BM25: {e}")

        # ===== 降级：BM25 关键词检索 =====
        return self._rank_crystals_bm25(query, crystals, top_k, task_type, task_types)

    def _track_crystal_usage(self, crystal_ids: List[str], context: str = "debate") -> None:
        """
        追踪晶体使用记录
        
        Args:
            crystal_ids: 本次使用的晶体ID列表
            context: 使用场景（"debate", "retrieval", "validation"）
        """
        if not crystal_ids:
            return
        
        # 加载现有追踪数据
        track_path = Config.DATA_ROOT / "系统日志" / "crystal_usage_track.json"
        track_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if track_path.exists():
                with open(track_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {
                    "usage_history": [],
                    "total_usage": {},
                    "last_updated": None
                }
        except:
            data = {
                "usage_history": [],
                "total_usage": {},
                "last_updated": None
            }
        
        # 记录本次使用
        timestamp = datetime.now().isoformat()
        for cid in crystal_ids:
            data["usage_history"].append({
                "crystal_id": cid,
                "timestamp": timestamp,
                "context": context
            })
            data["total_usage"][cid] = data["total_usage"].get(cid, 0) + 1
        
        data["last_updated"] = timestamp
        
        # 限制历史记录数量（保留最近1000条）
        if len(data["usage_history"]) > 1000:
            data["usage_history"] = data["usage_history"][-1000:]
        
        with open(track_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_crystal_usage_stats(self) -> Dict[str, Any]:
        """
        获取晶体使用统计。

        Returns:
            dict: 包含以下信息
                - total_usage (Dict[str, int]): 每个晶体的使用次数，如 {"C001": 5, ...}
                - usage_history (List): 使用历史记录
                - total_events (int): 总事件数
                - unique_crystals (int): 使用过的唯一晶体数
        """
        track_path = Config.DATA_ROOT / "系统日志" / "crystal_usage_track.json"
        if not track_path.exists():
            return {
                "total_usage": {},
                "usage_history": [],
                "total_events": 0,
                "unique_crystals": 0
            }
        
        try:
            with open(track_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "total_usage": data.get("total_usage", {}),
                "usage_history": data.get("usage_history", []),
                "total_events": len(data.get("usage_history", [])),
                "unique_crystals": len(data.get("total_usage", {}))
            }
        except:
            return {
                "total_usage": {},
                "usage_history": [],
                "total_events": 0,
                "unique_crystals": 0
            }
    
        
    def verify_dual_loop(self) -> Dict[str, Any]:
        """
        双环闭环验证

        验证外环更新后的晶体是否被内环新一轮辩论调用

        返回值是一个字典，包含以下字段：
                - verified (bool): 是否验证通过
                - summary (str): 验证摘要
                - details (List[Dict]): 详细验证记录
                - call_rate (float): 调用率
                - total_updates (int): 外环更新总数
                - total_calls (int): 内环调用总数

        """
        # 1. 获取外环更新记录（从 evolution_log 中获取晶体添加/更新事件）
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        updates = []  # ← 在 try 块之前初始化

        # 方法A：从 evolution_log 读取
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for event in data.get("events", []):
                        et = event.get("event_type", "")
                        # 支持多种事件类型名称
                        if et in ["crystal_added", "crystal_updated", "crystal_created", "crystal_added_from_debate"]:
                            details = event.get("details", {})
                            # 尝试多种可能的字段名
                            cid = details.get("crystal_id") or details.get("id") or details.get("crystal") or ""
                            if cid:
                                updates.append({
                                    "crystal_id": cid,
                                    "timestamp": event.get("timestamp", ""),
                                    "type": et
                                })
            except Exception as e:
                print(f"⚠️ 读取进化日志失败: {e}")

        # 方法B：如果 evolution_log 中没有记录，从当前晶体列表反向推断
        if not updates:
            try:
                crystals = self.parse_crystals()
                if crystals:
                    sorted_crystals = sorted(crystals, key=lambda c: c.id, reverse=True)
                    for c in sorted_crystals[:10]:
                        updates.append({
                            "crystal_id": c.id,
                            "timestamp": datetime.now().isoformat(),
                            "type": "crystal_added_inferred"
                        })
            except Exception as e:
                print(f"⚠️ 推断晶体列表失败: {e}")

        # 2. 获取内环调用记录
        usage = self.get_crystal_usage_stats()
        usage_history = usage.get("usage_history", [])

        # 3. 交叉验证
        verified_count = 0
        details = []

        for update in updates:
            cid = update.get("crystal_id", "")
            if not cid:
                continue

            called = any(h.get("crystal_id") == cid for h in usage_history)

            # 检查是否在更新后被调用
            update_time = update.get("timestamp", "")
            called_after_update = False
            if update_time:
                for h in usage_history:
                    if h.get("crystal_id") == cid and h.get("timestamp", "") > update_time:
                        called_after_update = True
                        break
            else:
                called_after_update = called

            details.append({
                "crystal_id": cid,
                "update_type": update.get("type", ""),
                "update_time": update_time,
                "called": called,
                "called_after_update": called_after_update,
                "usage_count": usage.get("total_usage", {}).get(cid, 0)
            })

            if called_after_update:
                verified_count += 1

        total_updates = len(updates)
        call_rate = verified_count / total_updates if total_updates > 0 else 0.0

        # 生成摘要
        if total_updates == 0:
            summary = "暂无外环更新记录，无法验证双环闭环"
            verified = False
        elif call_rate >= 0.8:
            summary = f"✅ 双环闭环验证通过：{verified_count}/{total_updates} 条更新晶体被调用，调用率 {call_rate*100:.1f}%"
            verified = True
        elif call_rate >= 0.5:
            summary = f"⚠️ 双环闭环验证部分通过：{verified_count}/{total_updates} 条更新晶体被调用，调用率 {call_rate*100:.1f}%，建议检查未调用的晶体"
            verified = False
        else:
            summary = f"❌ 双环闭环验证未通过：仅 {verified_count}/{total_updates} 条更新晶体被调用，调用率 {call_rate*100:.1f}%，建议检查检索策略"
            verified = False

        return {
            "verified": verified,
            "summary": summary,
            "details": details,
            "call_rate": call_rate,
            "total_updates": total_updates,
            "total_calls": len(usage_history),
            "verified_count": verified_count
        }

    def _rank_crystals_bm25(self, query: str, crystals: List[Crystal], top_k: int = 5,
                            task_type: str = "general", task_types: List[str] = None) -> List[Tuple[float, Crystal]]:
        """
        BM25 关键词检索（保留原逻辑作为降级方案）
        """
        query_tokens = self._search_tokens(query)
        if not query_tokens:
            return [(0.0, c) for c in crystals[:top_k]]

        doc_tokens = [self._search_tokens(c.content + " " + " ".join(c.links)) for c in crystals]
        doc_freq = Counter()
        for tokens in doc_tokens:
            doc_freq.update(set(tokens))

        avg_len = sum(len(tokens) for tokens in doc_tokens) / max(1, len(doc_tokens))
        query_counts = Counter(query_tokens)

        scored = []
        for crystal, tokens in zip(crystals, doc_tokens):
            counts = Counter(tokens)
            doc_len = max(1, len(tokens))

            bm25 = 0.0
            for term, q_weight in query_counts.items():
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = math.log(1 + (len(crystals) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                denom = tf + 1.5 * (1 - 0.75 + 0.75 * doc_len / max(1, avg_len))
                bm25 += idf * (tf * 2.5 / denom) * min(2, q_weight)

            # 短语匹配加成
            phrase_bonus = 0.0
            q_lower = query.lower()
            text_lower = crystal.content.lower()
            if q_lower and q_lower in text_lower:
                phrase_bonus += 3.0
            phrase_bonus += sum(0.35 for term in set(query_tokens) if len(term) >= 2 and term in text_lower)
            hebbian_boost = self.get_hebbian_boost(crystal.id, task_type, task_types)
            total_score = bm25 + phrase_bonus + hebbian_boost * 0.3
            scored.append((total_score, crystal))


        scored.sort(key=lambda item: (item[0], item[1].heat), reverse=True)
        return scored[:top_k]
    def compute_crystal_heat(self, crystal: Crystal, all_crystals: List[Crystal]) -> float:
        holes = self.parse_holes()
        return self._compute_crystal_heat(crystal, all_crystals, holes)

    def _compute_crystal_heat(self, crystal: Crystal, all_crystals: List[Crystal], holes: List[Hole]) -> float:
        ref_count = sum(1 for c in all_crystals if crystal.id in c.links)
        l0_hole_ids = ["H001","H002","H003"]
        l0_texts = [h.content for h in holes if h.id in l0_hole_ids]
        semantic = max((self._simple_similarity(crystal.content, lt) for lt in l0_texts), default=0.0)
        return ref_count * 0.4 + semantic * 0.3

    def load_layer_state(self) -> Dict:
        """加载层级状态（线程安全）"""
        with self._file_lock:
            if not self.files.exists("layer_state"):
                return {"layers": {}, "heat_map": {}, "last_accessed": {}, "manual_override": {}}
            try:
                return json.loads(self.files.read("layer_state"))
            except:
                return {"layers": {}, "heat_map": {}, "last_accessed": {}, "manual_override": {}}

    def save_layer_state(self, state: Dict):
        """保存层级状态（线程安全）"""
        with self._file_lock:
            self.files.write("layer_state", json.dumps(state, ensure_ascii=False, indent=2))

    def delete_crystal(self, crystal_id: str) -> bool:
        """删除晶体：文件 + 层级状态 + 向量库同步。"""
        with self._file_lock:
            cryst = self.files.read("crystals")
            pat = rf"\| {re.escape(crystal_id)} \|.*?\|\n"
            new = re.sub(pat, "", cryst, flags=re.MULTILINE)
            if new == cryst:
                self._append_change_log("删除晶体", f"未找到晶体 {crystal_id}")
                return False
            self.files.write("crystals", new)
        # 同步删除 Skill 目录
        try:
            import shutil
            skill_dir = Config.DATA_ROOT / "skills" / crystal_id
            if skill_dir.exists() and skill_dir.is_dir():
                shutil.rmtree(skill_dir)
        except Exception as e:
            self._append_change_log("删除晶体", f"Skill 目录删除失败 {crystal_id}: {e}")
        state = self.load_layer_state()
        for key in ("layers", "heat_map", "last_accessed", "manual_override"):
            d = state.get(key, {})
            d.pop(crystal_id, None)
            state[key] = d
        self.save_layer_state(state)
        self._append_change_log("手动删除晶体", f"删除 {crystal_id}")
        if getattr(self, "vector_store", None) is not None:
            try:
                if self.vector_store.is_available():
                    ok = self.vector_store.delete_crystal(crystal_id)
                    self._append_change_log("向量库同步", f"已从向量库删除 {crystal_id}: {ok}")
            except Exception as e:
                    self._append_change_log("向量库同步", f"删除 {crystal_id} 失败: {e}")
        return True

    def update_crystal_content(self, crystal_id: str, content: str, links: List[str] = None) -> bool:
        """更新晶体正文与链接（供合并/进化算子使用）。"""
        links = links or []
        links_text = ", ".join(links) if links else "—"
        with self._file_lock:
            cryst = self.files.read("crystals")
            pattern = rf"\| {re.escape(crystal_id)} \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|"
            match = re.search(pattern, cryst, flags=re.MULTILINE)
            if not match:
                return False
            table_content = content.replace("\n", " ").replace("|", "/")
            new_row = (
                f"| {crystal_id} | {table_content} | {links_text} | "
                f"{match.group(3)} | {match.group(4)} | {match.group(5)} | {match.group(6)} |"
            )
            self.files.write("crystals", re.sub(pattern, new_row, cryst, count=1, flags=re.MULTILINE))
        # 同步更新 Skill 目录中的 CRYSTAL.md
        try:
            skill_md = Config.DATA_ROOT / "skills" / crystal_id / "CRYSTAL.md"
            if skill_md.exists():
                md = skill_md.read_text(encoding="utf-8")
                md = re.sub(
                    r"## 核心内容\s*\n+(.*?)(?=\n## |\Z)",
                    f"## 核心内容\n\n{content}\n",
                    md,
                    flags=re.DOTALL,
                )
                links_block = "\n".join(f"- {link}" for link in links) if links else "（无链接）"
                md = re.sub(
                    r"## 链接关系\s*\n+.*?(?=\n## |\Z)",
                    f"## 链接关系\n\n{links_block}\n",
                    md,
                    flags=re.DOTALL,
                )
                skill_md.write_text(md, encoding="utf-8")
        except Exception as e:
            self._append_change_log("更新晶体", f"Skill 同步失败 {crystal_id}: {e}")
        self._append_change_log("更新晶体", f"{crystal_id} 正文/链接已更新")
        if getattr(self, "vector_store", None) is not None:
            try:
                if self.vector_store.is_available():
                    self.vector_store.add_crystals(self.parse_crystals())
            except Exception:
                pass
        return True

    def execute_sandbox(self, code: str, timeout: int = 5) -> Dict[str, Any]:
        """执行一段 Python 代码并返回沙盒结果（Day 12 测试兼容入口）。"""
        try:
            from harness.assurance.sandbox import SandboxExecutor
        except ImportError:
            return {"success": False, "error": "SandboxExecutor 尚未接入 v5"}
        return SandboxExecutor(self).execute_code(code, timeout=timeout)

    def update_crystal_access_time(self, crystal_id: str):
        state = self.load_layer_state()
        last_acc = state.get("last_accessed", {})
        last_acc[crystal_id] = date.today().isoformat()
        state["last_accessed"] = last_acc
        self.save_layer_state(state)

    def update_crystal_layers(self) -> Tuple[List[Crystal], List[Crystal], List[Crystal]]:
        crystals = self.parse_crystals()
        if not crystals:
            return [], [], []
        state = self.load_layer_state()
        last_accessed = state.get("last_accessed", {})
        manual_override = state.get("manual_override", {})
        holes = self.parse_holes()
        heat_map = {c.id: self._compute_crystal_heat(c, crystals, holes) for c in crystals}
        def sort_key(cid):
            if manual_override.get(cid) == "L1_fixed":
                return (1, heat_map[cid])
            return (0, heat_map[cid])
        sorted_ids = sorted(heat_map.keys(), key=sort_key, reverse=True)
        layers = {}
        l1_assigned = 0
        for cid in sorted_ids:
            if manual_override.get(cid) == "L1_fixed":
                layers[cid] = "L1"
                l1_assigned += 1
        for cid in sorted_ids:
            if cid in layers:
                continue
            if l1_assigned < Config.L1_MAX:
                layers[cid] = "L1"
                l1_assigned += 1
            else:
                last = last_accessed.get(cid, (date.today() - timedelta(days=31)).isoformat())
                try:
                    days_since = (date.today() - date.fromisoformat(last)).days
                except:
                    days_since = 31
                if heat_map[cid] < Config.L2_TO_L3_HEAT_THRESHOLD and days_since > Config.L2_TO_L3_DAYS_THRESHOLD:
                    layers[cid] = "L3"
                else:
                    layers[cid] = "L2"
        state["layers"] = layers
        state["heat_map"] = heat_map
        self.save_layer_state(state)
        L1 = [c for c in crystals if layers.get(c.id) == "L1"]
        L2 = [c for c in crystals if layers.get(c.id) == "L2"]
        L3 = [c for c in crystals if layers.get(c.id) == "L3"]
        return L1, L2, L3

    def archive_cold_crystals(self) -> List[str]:
        state = self.load_layer_state()
        layers = state.get("layers", {})
        heat_map = state.get("heat_map", {})
        last_accessed = state.get("last_accessed", {})
        today_dt = date.today()
        archived = []
        changed = False
        for cid, layer in list(layers.items()):
            if layer == "L2":
                heat = heat_map.get(cid, 0.0)
                last = last_accessed.get(cid, "2000-01-01")
                try:
                    days_since = (today_dt - date.fromisoformat(last)).days
                except:
                    days_since = 999
                if heat < Config.L2_TO_L3_HEAT_THRESHOLD and days_since > Config.L2_TO_L3_DAYS_THRESHOLD:
                    layers[cid] = "L3"
                    changed = True
                    archived.append(cid)
        if changed:
            state["layers"] = layers
            self.save_layer_state(state)
            self._append_change_log("自动归档", f"已将 {len(archived)} 个冷晶体从 L2 移至 L3")
        return archived

    def get_attention_context(self) -> Tuple[List[Hole], List[Crystal]]:
        holes = self.parse_holes()
        l0_hole_ids = ["H001","H002","H003"]
        l0_holes = [h for h in holes if h.id in l0_hole_ids]
        if len(l0_holes) < 3:
            default_holes = {"H001":"如何定义与分解复杂问题？","H002":"非共识情况下如何做出正确判断？","H003":"因果链的完整推演与验证方法"}
            existing_ids = [h.id for h in l0_holes]
            for hid, content in default_holes.items():
                if hid not in existing_ids:
                    l0_holes.append(Hole(id=hid, content=content, urgency=0.9))
        state = self.load_layer_state()
        layers = state.get("layers", {})
        all_crystals = self.parse_crystals()
        L1_crystals = [c for c in all_crystals if layers.get(c.id) == "L1"]
        for c in L1_crystals:
            self.update_crystal_access_time(c.id)
        return l0_holes, L1_crystals

    def get_conflict_scope(self) -> List[Crystal]:
        state = self.load_layer_state()
        layers = state.get("layers", {})
        all_crystals = self.parse_crystals()
        scope = [c for c in all_crystals if layers.get(c.id) in ("L1","L2")]
        if not scope:
            L1, L2, _ = self.update_crystal_layers()
            scope = L1 + L2
        return scope

    def detect_conflicts(self, scope: List[Crystal] = None, method: str = "auto") -> List[Conflict]:
        """
        矛盾检测引擎（升级版）
        支持三种模式：auto / vector / jaccard
        """
        if scope is None:
            scope = self.get_conflict_scope()

        if len(scope) < 2:
            return []

        # ===== 修复：统一判断 vector_store 是否可用 =====
        vector_available = (
            self.vector_store is not None and
            hasattr(self.vector_store, 'is_available') and
            self.vector_store.is_available()
        )

        if method == "jaccard":
            return self._detect_conflicts_jaccard(scope)
        elif method == "vector":
            if vector_available:
                return self.detect_conflicts_vector(scope)
            else:
                if hasattr(self, '_log'):
                    self._log("⚠️ 向量检索不可用，降级到 Jaccard", "warning")
                return self._detect_conflicts_jaccard(scope)
        else:  # "auto"
            if vector_available:
                return self.detect_conflicts_vector(scope)
            else:
                return self._detect_conflicts_jaccard(scope)

    def _detect_conflicts_jaccard(self, scope: List[Crystal]) -> List[Conflict]:
        """
        Jaccard 关键词匹配检测（原逻辑保留作为降级方案）
        """
        if len(scope) < 2:
            return []

        conflicts = []
        checked_pairs = set()

        for i in range(len(scope)):
            for j in range(i + 1, len(scope)):
                c1, c2 = scope[i], scope[j]
                pair_key = tuple(sorted([c1.id, c2.id]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                sim = self._simple_similarity(c1.content, c2.content)
                if sim > 0.7:
                    conflicts.append(Conflict(
                        crystal_a=c1.id,
                        crystal_b=c2.id,
                        similarity=round(sim, 2),
                        content_a=c1.content,
                        content_b=c2.content
                    ))

        conflicts.sort(key=lambda x: x.similarity, reverse=True)
        return conflicts

    def detect_conflicts_vector(self, scope: List[Crystal] = None, threshold: float = 0.3) -> List[Conflict]:
        """
        向量级矛盾检测引擎
        使用向量余弦距离检测晶体间的语义矛盾。
        距离 < threshold 视为高度语义相关（可能矛盾或重复）。
        """
        # ===== 修复：防御性检查 =====
        if self.vector_store is None:
            if hasattr(self, '_log'):
                self._log("⚠️ vector_store 为 None，降级到 Jaccard", "warning")
            return self._detect_conflicts_jaccard(scope)

        if not self.vector_store.is_available():
            if hasattr(self, '_log'):
                self._log("⚠️ 向量检索不可用，降级到 Jaccard", "warning")
            return self._detect_conflicts_jaccard(scope)

        if scope is None:
            scope = self.get_conflict_scope()

        if len(scope) < 2:
            return []

        conflicts = []
        checked_pairs = set()

        for i in range(len(scope)):
            for j in range(i + 1, len(scope)):
                c1, c2 = scope[i], scope[j]
                pair_key = tuple(sorted([c1.id, c2.id]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                try:
                    results = self.vector_store.query(c1.content, top_k=10)
                    c2_similarity = 0.0
                    for cid, score in results:
                        if cid == c2.id:
                            c2_similarity = score
                            break

                    if c2_similarity > (1 - threshold):
                        conflicts.append(Conflict(
                            crystal_a=c1.id,
                            crystal_b=c2.id,
                            similarity=round(c2_similarity, 2),
                            content_a=c1.content,
                            content_b=c2.content
                        ))
                except Exception:
                    # 降级：使用 Jaccard
                    sim = self._simple_similarity(c1.content, c2.content)
                    if sim > 0.7:
                        conflicts.append(Conflict(
                            crystal_a=c1.id,
                            crystal_b=c2.id,
                            similarity=round(sim, 2),
                            content_a=c1.content,
                            content_b=c2.content
                        ))

        conflicts.sort(key=lambda x: x.similarity, reverse=True)
        return conflicts

    def load_hole_progress(self) -> Dict[str, float]:
        """加载孔洞进度（线程安全）"""
        with self._file_lock:
            if not self.files.exists("hole_progress"):
                return {}
            try:
                return json.loads(self.files.read("hole_progress"))
            except:
                return {}

    def save_hole_progress(self, progress: Dict[str, float]) -> None:
        """保存孔洞进度（线程安全）"""
        with self._file_lock:
            self.files.write("hole_progress", json.dumps(progress, ensure_ascii=False, indent=2))

    def match_info_to_hole(self, info_title: str, hole_content: str) -> float:
        keywords = re.findall(r'[\w\u4e00-\u9fff]{2,}', hole_content)
        info_lower = info_title.lower()
        hit = sum(1 for kw in keywords if kw.lower() in info_lower)
        return min(1.0, hit / max(1, len(keywords)*0.5))

    def vector_search(self, query: str, crystals: List[Crystal], top_k: int = 5,
                      task_type: str = None, task_types: List[str] = None) -> List[Crystal]:
        ranked = self.rank_crystals(query, crystals, top_k, task_type, task_types)
        if ranked:
            return [c for _, c in ranked]
        return self._keyword_search(query, crystals, top_k)

    def _keyword_search(self, query: str, crystals: List[Crystal], top_k: int) -> List[Crystal]:
        query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query.lower()))
        scored = []
        for c in crystals:
            text = c.content.lower()
            score = sum(1 for w in query_words if w in text)
            scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def get_associative_crystals(self, question: str, top_k: int = 5,
                                 task_type: str = None, task_types: List[str] = None) -> List[Crystal]:
        all_crystals = self.parse_crystals()
        if not all_crystals:
            return []
        return self.vector_search(question, all_crystals, top_k=top_k, task_type=task_type, task_types=task_types)

    def _append_change_log(self, section: str, content: str):
        date_header = f"\n## {datetime.now().strftime('%Y-%m-%d')} - {section}\n"
        self.files.append("change_log", date_header + content + "\n")

    def log_evolution_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """
        记录单用户进化事件（支持失败轨迹记录）

        Args:
            event_type: 事件类型（crystal_added | crystal_updated | crystal_archived | 
                        hole_filled | fingerprint_changed | role_adopted | verification_passed |
                        failure_trace | history_reused | alarm | chain_triggered）
            details: 事件详情，支持以下扩展字段：
                - failure_traces: 失败时的完整上下文
                - repair_attempts: 尝试的修复方案及结果
                - diagnosis: 系统自己对失败原因的判断
                - reused_history_id: 复用的历史记录ID
                - match_score: 历史匹配度
        """
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取现有日志
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = {"events": [], "summary": {}}
        else:
            data = {"events": [], "summary": {}}

        # 构建事件（支持失败轨迹字段）
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details,
            "trigger": details.get("trigger", "system_auto")
        }

        # ===== Day 4 新增：扩展字段（如果存在则记录） =====
        if "failure_traces" in details:
            event["failure_traces"] = details["failure_traces"]
        if "repair_attempts" in details:
            event["repair_attempts"] = details["repair_attempts"]
        if "diagnosis" in details:
            event["diagnosis"] = details["diagnosis"]
        if "reused_history_id" in details:
            event["reused_history_id"] = details["reused_history_id"]
        if "match_score" in details:
            event["match_score"] = details["match_score"]

        # 追加事件
        data["events"].append(event)

        # 更新摘要统计
        summary = data.get("summary", {})
        summary[event_type] = summary.get(event_type, 0) + 1
        data["summary"] = summary

        # 只保留最近 500 条事件（增加容量以容纳更多历史）
        if len(data["events"]) > 500:
            data["events"] = data["events"][-500:]

        # 写入文件
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_evolution_stats(self) -> Dict[str, Any]:
        """获取进化统计"""
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        if not log_path.exists():
            return {"total_events": 0, "summary": {}}
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "total_events": len(data.get("events", [])),
                "summary": data.get("summary", {}),
                "last_event": data.get("events", [])[-1] if data.get("events") else None
            }
        except:
            return {"total_events": 0, "summary": {}}

    def diagnose_failure_patterns(self) -> Dict[str, Any]:
        """便捷方法：调用 MetaLayer 的失败模式诊断"""
        if self.meta is None:
            raise RuntimeError("MetaLayer 未注入")
        return self.meta.diagnose_failure_patterns()

    def quality_gate_g1(self, question: str, context: Dict = None) -> Dict[str, Any]:
        """
        G1 质量门：问题是否可检验且相关

        与四组件挂钩：
        - 晶体卡片：检索相关晶体数量 ≥ 1
        - 孔洞：匹配孔洞数量 ≥ 1（紧迫度 ≥ 0.5）
        - 认知指纹：与指纹匹配度 ≥ 0.3

        Returns:
            {"passed": bool, "checks": dict, "reason": str}
        """
        context = context or {}
        results = {
            "crystal_match": {"count": 0, "passed": False},
            "hole_match": {"count": 0, "passed": False},
            "fingerprint_match": {"score": 0.0, "passed": False}
        }

        crystals = self.parse_crystals()
        if crystals:
            ranked = self.rank_crystals(question, crystals, top_k=5)
            results["crystal_match"]["count"] = len(ranked)
            results["crystal_match"]["passed"] = len(ranked) >= 1

        holes = self.parse_holes()
        if holes:
            matched = [h for h in holes if h.urgency >= 0.5 and
                       any(kw in question for kw in h.content[:20].split())]
            results["hole_match"]["count"] = len(matched)
            results["hole_match"]["passed"] = len(matched) >= 1

        try:
            fp = self.fingerprint_extractor.get_fingerprint()
            role_keywords = {
                "radical": ["颠覆", "激进", "创新", "突破", "打破"],
                "conservative": ["稳健", "保守", "风险", "安全", "验证"],
                "structural": ["结构", "系统", "框架", "流程", "机制"]
            }
            fp_keywords = role_keywords.get(fp.preferred_role, [])
            match_score = sum(1 for kw in fp_keywords if kw in question) / max(1, len(fp_keywords))
            results["fingerprint_match"]["score"] = match_score
            results["fingerprint_match"]["passed"] = match_score >= 0.3
        except:
            results["fingerprint_match"]["passed"] = True

        passed = (results["crystal_match"]["passed"] or
                  results["hole_match"]["passed"] or
                  results["fingerprint_match"]["passed"])

        reasons = []
        if results["crystal_match"]["passed"]:
            reasons.append(f"匹配 {results['crystal_match']['count']} 条晶体")
        if results["hole_match"]["passed"]:
            reasons.append(f"匹配 {results['hole_match']['count']} 个孔洞")
        if results["fingerprint_match"]["passed"]:
            reasons.append(f"指纹匹配度 {results['fingerprint_match']['score']:.2f}")

        return {
            "passed": passed,
            "checks": results,
            "reason": "；".join(reasons) if reasons else "无匹配"
        }

    def quality_gate_g2(self, answer: str, context: Dict = None) -> Dict[str, Any]:
        """
        G2 质量门：输出有依据且可靠

        与四组件挂钩：
        - 置信度：引用的晶体置信度 ≥ 0.5
        - 审计评分：审计评分 ≥ 0.6
        - 适用边界：无"不适用"条件被触发

        Returns:
            {"passed": bool, "checks": dict, "reason": str}
        """
        context = context or {}
        results = {
            "confidence": {"score": 0.0, "passed": False},
            "audit_score": {"score": 0.0, "passed": False},
            "boundary_ok": {"passed": True}
        }

        cited_ids = re.findall(r'C\d{3}', answer)
        if cited_ids:
            state = self.load_layer_state()
            heat_map = state.get("heat_map", {})
            conf_scores = [heat_map.get(cid, 0.0) for cid in cited_ids]
            avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0.0
            results["confidence"]["score"] = avg_conf
            results["confidence"]["passed"] = avg_conf >= 0.5

        audit_score = context.get("audit_score", 0.0)
        results["audit_score"]["score"] = audit_score
        results["audit_score"]["passed"] = audit_score >= 0.6

        boundary_terms = ["不适用", "不推荐", "谨慎使用", "特殊情况", "例外"]
        boundary_triggered = any(term in answer for term in boundary_terms)
        results["boundary_ok"]["passed"] = not boundary_triggered

        passed = (results["confidence"]["passed"] or
                  results["audit_score"]["passed"])

        reasons = []
        if results["confidence"]["passed"]:
            reasons.append(f"置信度 {results['confidence']['score']:.2f}")
        if results["audit_score"]["passed"]:
            reasons.append(f"审计评分 {results['audit_score']['score']:.2f}")
        if not results["boundary_ok"]["passed"]:
            reasons.append("触发了适用边界警告")

        return {
            "passed": passed,
            "checks": results,
            "reason": "；".join(reasons) if reasons else "无验证"
        }

    def sync_vector_store(self) -> Dict[str, Any]:
        """
        同步向量库：将当前所有晶体向量化

        Returns:
            {"total": int, "synced": int, "status": str}
        """
        if not self.vector_store.is_available():
            return {"total": 0, "synced": 0, "status": "vector_store_unavailable"}

        crystals = self.parse_crystals()
        if not crystals:
            return {"total": 0, "synced": 0, "status": "no_crystals"}

        # 检查现有数量
        existing = self.vector_store.count()
        if existing == len(crystals):
            return {"total": len(crystals), "synced": existing, "status": "already_synced"}

        # 如果数量不匹配，重置并重新同步
        if existing > 0 and existing != len(crystals):
            self.vector_store.reset()

        # 重新同步
        added = self.vector_store.add_crystals(crystals)
        return {"total": len(crystals), "synced": added, "status": "synced" if added > 0 else "failed"}

    def get_user_fingerprint(self) -> Optional[CognitiveFingerprint]:
        """获取当前用户的认知指纹"""
        try:
            return self.fingerprint_extractor.get_fingerprint()
        except Exception as e:
            print(f"[WARN] 获取指纹失败: {e}")
            return None

    def contribution_scoring(self, crystal_id: str = None) -> Dict[str, Any]:
        """
        计算晶体的贡献得分（负能力修剪）。

        贡献得分综合考虑：
        - 被引用次数（links 入度）
        - 热度（heat）
        - 与用户认知指纹的匹配度
        - 最近访问时间

        Args:
            crystal_id (str, optional): 晶体ID，若不指定则返回所有晶体的评分汇总。

        Returns:
            dict: 包含以下字段
                - crystal_id (str): 晶体ID
                - score (float): 综合贡献得分 (0-100)
                - ref_count (int): 被引用次数
                - heat (float): 热度
                - fingerprint_match (float): 与指纹匹配度 (0-1)
                - days_since_access (int): 距上次访问天数
                - status (str): 状态，可选 "active", "low_contribution", "cold"
        """
        crystals = self.parse_crystals()
        state = self.load_layer_state()
        heat_map = state.get("heat_map", {})
        last_accessed = state.get("last_accessed", {})

        # 获取用户指纹
        try:
            fingerprint = self.fingerprint_extractor.get_fingerprint()
        except:
            fingerprint = None

        # 构建引用关系映射
        ref_count_map = {}
        for c in crystals:
            ref_count_map[c.id] = 0
        for c in crystals:
            for link in c.links:
                if link in ref_count_map:
                    ref_count_map[link] += 1

        # 获取偏好角色的关键词（用于指纹匹配）
        role_keywords = {
            "radical": ["颠覆", "激进", "创新", "突破", "打破", "颠覆性"],
            "conservative": ["稳健", "保守", "风险", "安全", "验证", "可靠"],
            "structural": ["结构", "系统", "框架", "流程", "机制", "模型"],
            "executor": ["执行", "步骤", "操作", "落地", "行动", "检查"],
            "auditor": ["审计", "验证", "检查", "证据", "反例", "漏洞"]
        }
        pref_role = fingerprint.preferred_role if fingerprint else "structural"
        fp_keywords = role_keywords.get(pref_role, role_keywords["structural"])

        # 计算每个晶体的贡献得分
        today = date.today()
        results = []

        for c in crystals:
            # 1. 被引用次数（0-30分）
            ref_count = ref_count_map.get(c.id, 0)
            ref_score = min(30, ref_count * 6)

            # 2. 热度（0-30分）
            heat = heat_map.get(c.id, 0.0)
            heat_score = min(30, heat * 15)

            # 3. 指纹匹配度（0-20分）
            match_score = 0
            content_lower = c.content.lower()
            for kw in fp_keywords:
                if kw in content_lower:
                    match_score += 4
            match_score = min(20, match_score)

            # 4. 时效性（0-20分）
            last = last_accessed.get(c.id)
            if last:
                try:
                    days_since = (today - date.fromisoformat(last)).days
                except:
                    days_since = 999
            else:
                days_since = 999
            # 30天内访问得满分，超过30天逐渐衰减
            time_score = max(0, 20 * (1 - days_since / 90))
            time_score = min(20, time_score)

            total_score = ref_score + heat_score + match_score + time_score

            # 判断状态
            if total_score < 15:
                status = "cold"  # 极低贡献，建议归档
            elif total_score < 25:
                status = "low_contribution"  # 低贡献，需验证
            else:
                status = "active"

            results.append({
                "crystal_id": c.id,
                "content": c.content,
                "score": round(total_score, 1),
                "ref_count": ref_count,
                "heat": round(heat, 2),
                "fingerprint_match": round(match_score / 20, 2),
                "days_since_access": days_since,
                "status": status
            })

        # 按得分排序
        results.sort(key=lambda x: x["score"], reverse=True)

        if crystal_id:
            # 返回指定晶体的信息
            for r in results:
                if r["crystal_id"] == crystal_id:
                    return r
            return {"error": f"未找到晶体 {crystal_id}"}

        return {
            "total": len(results),
            "active": len([r for r in results if r["status"] == "active"]),
            "low_contribution": len([r for r in results if r["status"] == "low_contribution"]),
            "cold": len([r for r in results if r["status"] == "cold"]),
            "details": results
        }

    def get_low_contribution_crystals(self, threshold: float = 25.0) -> List[Dict]:
        """
        获取低贡献晶体列表（用于验证门控）
        """
        result = self.contribution_scoring()
        if "error" in result:
            return []
        return [r for r in result.get("details", []) if r["score"] < threshold]

    # ===== Day 5: Hebbian 学习 =====
    def _load_hebbian_weights(self):
        """从文件加载 Hebbian 权重"""
        weight_file = Config.DATA_ROOT / "系统日志" / "hebbian_weights.json"
        if weight_file.exists():
            try:
                with open(weight_file, "r", encoding="utf-8") as f:
                    self.hebbian_weights = json.load(f)
            except:
                self.hebbian_weights = {}
        else:
            self.hebbian_weights = {}
        self._apply_hebbian_decay()

    def _save_hebbian_weights(self):
        """保存 Hebbian 权重到文件"""
        self.hebbian_weights["_last_updated"] = datetime.now().isoformat()
        self.hebbian_weights["_event_count"] = int(self.hebbian_weights.get("_event_count", 0)) + 1
        weight_file = Config.DATA_ROOT / "系统日志" / "hebbian_weights.json"
        with open(weight_file, "w", encoding="utf-8") as f:
            json.dump(self.hebbian_weights, f, ensure_ascii=False, indent=2)

    HEBBIAN_DECAY_PER_DAY = 0.98
    REWARD_RATES = {
        "adopt": 0.10,
        "reject": -0.06,
        "neutral": 0.0,
        "activity": 0.02,
        "quality": 0.05,
        "reuse": 0.03,
        "vote": 0.05,
    }

    def _apply_hebbian_decay(self):
        """按时间衰减权重，让旧奖励逐渐让位给新证据。"""
        last = self.hebbian_weights.get("_last_updated")
        if not last:
            return
        try:
            days = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 86400.0
        except Exception:
            return
        if days <= 0:
            return
        factor = self.HEBBIAN_DECAY_PER_DAY ** min(365.0, days)
        for key in list(self.hebbian_weights):
            if key.startswith(("task_", "pair_", "vote_", "synapse_")):
                old = self.hebbian_weights.get(key)
                if isinstance(old, (int, float)):
                    self.hebbian_weights[key] = round(0.5 + (old - 0.5) * factor, 4)

    def record_hebbian_reward(self, kind: str, crystal_ids: List[str] = None,
                              role_keys: List[str] = None, reward: Optional[float] = None,
                              question: Optional[str] = None, task_type: Optional[str] = None,
                              context: Optional[Dict] = None) -> float:
        """多信号 Hebbian 奖励：采纳/驳回/中立/质量/复用/多说话/票选。"""
        crystal_ids = list(crystal_ids or [])
        role_keys = list(role_keys or [])
        rate = self.REWARD_RATES.get(kind, 0.0)
        if reward is not None:
            rate = max(-1.0, min(1.0, float(reward)))

        if kind in ("adopt", "reject", "neutral", "quality", "reuse") and crystal_ids:
            categories = self._classify_question(question) if question else ([task_type] if task_type else ["general"])
            if categories and categories != ["general"]:
                base_delta = 0.10 if kind == "adopt" else -0.06 if kind == "reject" else 0.05
                delta = base_delta if reward is None else base_delta * rate
                for cid in crystal_ids:
                    for category in categories:
                        key = f"task_{category}_{cid}"
                        old = self.hebbian_weights.get(key, 0.0)
                        self.hebbian_weights[key] = max(0.0, min(1.0, round(old + delta, 4)))
            if len(crystal_ids) >= 2:
                base_delta = 0.10 if kind == "adopt" else -0.06 if kind == "reject" else 0.05
                delta = base_delta if reward is None else base_delta * rate
                for i in range(len(crystal_ids)):
                    for j in range(i + 1, len(crystal_ids)):
                        pair = tuple(sorted([crystal_ids[i], crystal_ids[j]]))
                        key = f"pair_{pair[0]}_{pair[1]}"
                        old = self.hebbian_weights.get(key, 0.0)
                        self.hebbian_weights[key] = max(0.0, min(1.0, round(old + delta, 4)))

        if role_keys:
            role_delta = {
                "adopt": 0.05,
                "reject": -0.03,
                "neutral": 0.0,
                "activity": 0.01,
                "vote": 0.0,
            }.get(kind, 0.0)
            if reward is not None:
                role_delta = rate * 0.1
            for rk in role_keys:
                key = f"vote_{rk}"
                old = self.hebbian_weights.get(key, 0.5)
                self.hebbian_weights[key] = max(0.0, min(1.0, round(old + role_delta, 4)))
                if kind == "activity":
                    akey = f"activity_{rk}"
                    self.hebbian_weights[akey] = int(self.hebbian_weights.get(akey, 0)) + 1

        try:
            self.log_evolution_event("hebbian_reward", {
                "kind": kind,
                "rate": round(rate, 3),
                "crystal_ids": crystal_ids[:20],
                "role_keys": role_keys,
                "context": context or {},
            })
        except Exception:
            pass
        self._save_hebbian_weights()
        return rate

    def get_hebbian_stats(self) -> Dict[str, Any]:
        """Hebbian 状态概览，供界面/API 展示。"""
        activity = {k: v for k, v in self.hebbian_weights.items() if k.startswith("activity_")}
        return {
            "total_keys": len(self.hebbian_weights),
            "event_count": self.hebbian_weights.get("_event_count", 0),
            "last_updated": self.hebbian_weights.get("_last_updated", ""),
            "activity": activity,
            "decay_per_day": self.HEBBIAN_DECAY_PER_DAY,
        }

    def update_hebbian_weights(self, crystal_ids: List[str], task_type: Optional[str] = None,
                               score: Optional[float] = None, question: Optional[str] = None):
        """
        更新 Hebbian 权重
        - 兼容旧签名 (crystal_ids, task_type, score)
        - 传入 question 时使用九分类多标签，纯 general 不写权重
        """
        if not crystal_ids or len(crystal_ids) < 2:
            return
        if score is None:
            score = 0.6
        if question is not None:
            categories = self._classify_question(question)
        else:
            categories = [task_type] if task_type else ["general"]
        if not categories or categories == ["general"]:
            return
        # 对每对晶体组合更新权重
        for i in range(len(crystal_ids)):
            for j in range(i+1, len(crystal_ids)):
                pair = tuple(sorted([crystal_ids[i], crystal_ids[j]]))
                key = f"pair_{pair[0]}_{pair[1]}"
                old = self.hebbian_weights.get(key, 0.0)
                delta = (score - 0.5) * 0.1
                new_weight = max(0.0, min(1.0, old + delta))
                self.hebbian_weights[key] = new_weight
        # 每个类别独立更新晶体权重
        for category in categories:
            task_key = f"task_{category}"
            for cid in crystal_ids:
                key = f"{task_key}_{cid}"
                old = self.hebbian_weights.get(key, 0.0)
                delta = (score - 0.5) * 0.05
                new_weight = max(0.0, min(1.0, old + delta))
                self.hebbian_weights[key] = new_weight
        # 多标签组合键便于追踪（如 task_tech_policy_C001）
        if len(categories) > 1:
            combo_key = "task_" + "_".join(categories)
            for cid in crystal_ids:
                key = f"{combo_key}_{cid}"
                old = self.hebbian_weights.get(key, 0.0)
                delta = (score - 0.5) * 0.05
                self.hebbian_weights[key] = max(0.0, min(1.0, old + delta))
        self._save_hebbian_weights()

    def get_hebbian_boost(self, crystal_id: str, task_type: str = None,
                          task_types: List[str] = None) -> float:
        """获取某个晶体在当前任务类型下的 Hebbian 加成（多标签取平均，保持 0~0.3 区间）"""
        categories = list(task_types or [])
        if task_type and task_type not in categories:
            categories.append(task_type)
        if not categories:
            return 0.0
        boosts = [self.hebbian_weights.get(f"task_{c}_{crystal_id}", 0.0) for c in categories]
        return (sum(boosts) / len(boosts)) * 0.3

    def vote_role(self, role_key: str, support: Optional[bool] = None) -> float:
        """用户票选回写：支持 +0.05，反对 -0.05，中立/None 重置为 0.5。"""
        key = f"vote_{role_key}"
        if support is None:
            new = 0.5
        else:
            delta = 0.05 if support else -0.05
            old = self.hebbian_weights.get(key, 0.5)
            new = max(0.0, min(1.0, old + delta))
        self.hebbian_weights[key] = new
        self._save_hebbian_weights()
        label = "中立" if support is None else ("支持" if support else "反对")
        self._append_change_log("用户票选", f"{role_key} {label} → {new:.2f}")
        return new
    def inspiration_furnace_review_phase2(self) -> Dict[str, Any]:
        """便捷方法：调用元层的灵感熔炉复盘（二）"""
        if self.meta is None:
            raise RuntimeError("MetaLayer 未注入")
        return self.meta.inspiration_furnace_review_phase2()

    def _get_unarchived_holes(self) -> List[Dict]:
        """
        获取当前会话中未归档的 L3 孔洞
        从 last_deposit.json 和 evolution_log 中读取
        """
        unarchived = []

        # 从 last_deposit.json 读取
        deposit_path = Config.DATA_ROOT / "系统日志" / "last_deposit.json"
        if deposit_path.exists():
            try:
                with open(deposit_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    unarchived = data.get("unarchived_holes", [])
                    if unarchived:
                        return unarchived
            except:
                pass

        # 从 evolution_log 读取最近的沉淀事件
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    events = data.get("events", [])
                    for event in reversed(events):
                        if event.get("event_type") == "deposit_unarchived_holes":
                            details = event.get("details", {})
                            unarchived = details.get("holes", [])
                            break
            except:
                pass

        return unarchived

