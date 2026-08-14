#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from core.models import TaskCard
from evolution.godel import GödelAgent
from governance.config import Config
from governance.prompt_templates import PromptTemplate, PromptTemplateManager

class MetaLayer:
    """
    认知晶体树的元层引擎

    负责管理"如何管理认知"的六种元原语。
    与工作层（CrystalEngine）分离，实现双层架构。

    对应建议1：建立"工作层+元层"双层架构
    """

    def __init__(
        self,
        engine: Any,
        file_io: Any,
        ai_client=None,
        force_explorer_factory: Any = None,
        anti_fraud_providers: Any = None,
        planner_factory: Any = None,
    ):
        self.engine = engine
        self.files = file_io
        self.ai_client = ai_client  # 新增
        self.force_explorer_factory = force_explorer_factory
        self.anti_fraud_providers = anti_fraud_providers
        self.planner_factory = planner_factory
        self.primitive_states = {
            "active_gap_detection": {"last_run": None, "status": "idle"},
            "temporal_aware_escalation": {"last_run": None, "status": "idle"},
            "layer_aware_calibration": {"last_run": None, "status": "active"},
            "sleep_consolidation": {"last_run": None, "status": "idle"},
            "distributed_metacognition": {"last_run": None, "status": "disabled"},
            "validation_gated_self_evolution": {"last_run": None, "status": "active"}
        }
        self._read_meta_state("meta_state.json", self.primitive_states, "primitive_states")
        # Day 3 新增：触发链执行状态
        self.chain_states = {
            "isolated_crystal_to_validation": {"last_triggered": None, "trigger_count": 0},
            "stale_hot_to_gap_detection": {"last_triggered": None, "trigger_count": 0},
        }
        self._read_meta_state("meta_chain_state.json", self.chain_states, "chain_states")
        self.force_explorer = (
            force_explorer_factory(engine, self._log, ai_client)
            if force_explorer_factory
            else None
        )
        # ===== Day 16: 初始化 Gödel Agent =====
        self.template_manager = PromptTemplateManager(file_io)
        self.gödel_agent = GödelAgent(
            engine,
            ai_client,
            self.template_manager,
            planner_factory=planner_factory,
        )
       
    def _log(self, msg: str, level: str = "system"):
        """日志辅助方法"""
        if hasattr(self.engine, '_append_change_log'):
            self.engine._append_change_log("元层日志", msg)
        print(f"[{level.upper()}] {msg}")    
        
    def _load_pareto_data(self) -> Dict[str, Any]:
        """加载帕累托数据"""
        pareto_path = Config.DATA_ROOT / "系统日志" / "pareto_frontier.json"
        if pareto_path.exists():
            try:
                with open(pareto_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"configs": {}, "history": [], "daily_stats": []}

    def _save_pareto_data(self, data: Dict[str, Any]) -> None:
        """保存帕累托数据"""
        pareto_path = Config.DATA_ROOT / "系统日志" / "pareto_frontier.json"
        pareto_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pareto_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_conversation_metrics(
        self,
        profile_name: str,
        accuracy: float,
        cost: float,
        latency: float,
        crystal_refs: int = 0,
        quality_score: float = 0.0
    ) -> None:
        """
        记录一次对话的三维指标

        Args:
            profile_name: 配置名称 (high_accuracy/balanced/economy)
            accuracy: 准确性评分 (0-1)
            cost: 成本 (美元)
            latency: 延迟 (秒)
            crystal_refs: 晶体引用数
            quality_score: 质量评分 (0-1)
        """
        data = self._load_pareto_data()

        # 更新配置记录
        if profile_name not in data["configs"]:
            data["configs"][profile_name] = {
                "accuracy": 0.0,
                "cost": 0.0,
                "latency": 0.0,
                "crystal_refs": 0,
                "quality_score": 0.0,
                "count": 0
            }

        config = data["configs"][profile_name]
        config["accuracy"] = (config["accuracy"] * config["count"] + accuracy) / (config["count"] + 1)
        config["cost"] = (config["cost"] * config["count"] + cost) / (config["count"] + 1)
        config["latency"] = (config["latency"] * config["count"] + latency) / (config["count"] + 1)
        config["crystal_refs"] = (config["crystal_refs"] * config["count"] + crystal_refs) / (config["count"] + 1)
        config["quality_score"] = (config["quality_score"] * config["count"] + quality_score) / (config["count"] + 1)
        config["count"] += 1

        # 添加到历史
        data["history"].append({
            "timestamp": datetime.now().isoformat(),
            "profile": profile_name,
            "accuracy": accuracy,
            "cost": cost,
            "latency": latency,
            "crystal_refs": crystal_refs,
            "quality_score": quality_score
        })

        # 限制历史数量
        if len(data["history"]) > Config.PARETO_HISTORY_LIMIT:
            data["history"] = data["history"][-Config.PARETO_HISTORY_LIMIT:]

        self._save_pareto_data(data)

    def get_pareto_status(self) -> Dict[str, Any]:
        """获取当前帕累托状态"""
        data = self._load_pareto_data()
        configs = data.get("configs", {})
        history = data.get("history", [])

        # 计算趋势
        trends = self._calculate_trends(history)

        return {
            "configs": configs,
            "history_count": len(history),
            "trends": trends,
            "best_profile": self._get_best_profile(configs),
            "daily_stats": data.get("daily_stats", [])
        }

    def _calculate_trends(self, history: List[Dict]) -> Dict[str, Any]:
        """计算趋势指标"""
        if len(history) < 3:
            return {"trend": "insufficient_data", "accuracy_delta": 0, "cost_delta": 0}

        recent = history[-10:]
        if len(recent) < 3:
            return {"trend": "stable", "accuracy_delta": 0, "cost_delta": 0}

        # 计算最近3条和之前3条的平均值
        first_half = recent[:len(recent)//2]
        second_half = recent[len(recent)//2:]

        avg_acc_first = sum(h.get("accuracy", 0) for h in first_half) / max(1, len(first_half))
        avg_acc_second = sum(h.get("accuracy", 0) for h in second_half) / max(1, len(second_half))
        avg_cost_first = sum(h.get("cost", 0) for h in first_half) / max(1, len(first_half))
        avg_cost_second = sum(h.get("cost", 0) for h in second_half) / max(1, len(second_half))

        acc_delta = avg_acc_second - avg_acc_first
        cost_delta = avg_cost_second - avg_cost_first

        if acc_delta > 0.05:
            trend = "improving"
        elif acc_delta < -0.05:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "accuracy_delta": round(acc_delta, 3),
            "cost_delta": round(cost_delta, 3),
            "avg_accuracy": round(avg_acc_second, 3),
            "avg_cost": round(avg_cost_second, 3)
        }

    def _get_best_profile(self, configs: Dict) -> Optional[str]:
        """获取当前最优配置"""
        if not configs:
            return None

        best = None
        best_score = -1

        for name, data in configs.items():
            # 综合评分：准确性权重0.5，成本权重0.3，延迟权重0.2
            score = (
                data.get("accuracy", 0) * 0.5 +
                (1 - min(1, data.get("cost", 0) * 10)) * 0.3 +
                (1 - min(1, data.get("latency", 0) / 60)) * 0.2
            )
            if score > best_score:
                best_score = score
                best = name

        return best

    def record_daily_stats(self, stats: Dict[str, Any]) -> None:
        """记录每日统计（个人认知效率仪表盘）"""
        data = self._load_pareto_data()

        if "daily_stats" not in data:
            data["daily_stats"] = []

        today = datetime.now().date().isoformat()
        # 检查今天是否已有记录
        existing = None
        for i, entry in enumerate(data["daily_stats"]):
            if entry.get("date") == today:
                existing = i
                break

        if existing is not None:
            # 更新已有记录
            data["daily_stats"][existing].update(stats)
            data["daily_stats"][existing]["date"] = today
        else:
            # 新增记录
            data["daily_stats"].append({"date": today, **stats})

        # 只保留最近30天
        if len(data["daily_stats"]) > 30:
            data["daily_stats"] = data["daily_stats"][-30:]

        self._save_pareto_data(data)

    def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取最近N天的每日统计"""
        data = self._load_pareto_data()
        daily = data.get("daily_stats", [])
        return daily[-days:]

    def _read_meta_state(self, filename: str, target: Dict[str, Any], key: str) -> None:
        """从 change_log 目录读取 JSON 状态文件，并合并进目标状态字典。"""
        state_file = self.files.resolve("change_log").parent / filename
        if not state_file.exists():
            return
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            target.update(data.get(key, {}))
        except Exception:
            pass

    def _write_meta_state(self, filename: str, key: str, data: Dict[str, Any]) -> None:
        """把状态字典写入 change_log 目录 JSON 文件，并附带保存时间戳。"""
        state_file = self.files.resolve("change_log").parent / filename
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(
                {key: data, "last_saved": datetime.now().isoformat()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def active_gap_detection(self) -> Dict[str, Any]:
        """
        主动检测晶体之间的逻辑缝隙
        返回：字典，包含 gaps, stats, trigger_info
        """
        if not Config.META_PRIMITIVES["active_gap_detection"]["enabled"]:
            return {
                "gaps": [],
                "stats": {"total": 0, "isolated_count": 0, "near_dup_count": 0},
                "trigger_info": {"isolated_crystal_count": 0, "has_isolated_crystals": False}
            }

        crystals = self.engine.parse_crystals()
        if len(crystals) < 20:
            return {
                "gaps": [],
                "stats": {"total": 0, "isolated_count": 0, "near_dup_count": 0},
                "trigger_info": {"isolated_crystal_count": 0, "has_isolated_crystals": False}
            }

        gaps = []

        # ===== 使用 detect_conflicts（内部会自动判断并降级） =====
        conflicts = self.engine.detect_conflicts(method="auto")

        # 将冲突转换为缺口
        for conflict in conflicts:
            if conflict.similarity > 0.7:
                gaps.append({
                    "type": "near_duplicate",
                    "crystal_a": conflict.crystal_a,
                    "crystal_b": conflict.crystal_b,
                    "similarity": conflict.similarity,
                    "severity": "high" if conflict.similarity > 0.85 else "medium",
                    "suggestion": f"考虑合并 {conflict.crystal_a} 和 {conflict.crystal_b} 或建立链接"
                })

        # 检测孤立晶体（links 为空的晶体）
        isolated = [c for c in crystals if not getattr(c, 'links', [])]
        for c in isolated:
            gaps.append({
                "type": "isolated_crystal",
                "crystal_id": c.id,
                "content": c.content,
                "severity": "medium",
                "suggestion": f"尝试将 {c.id} 与已有晶体建立链接"
            })

        if gaps:
            self.engine._append_change_log(
                "主动缺口检测",
                f"发现 {len(gaps)} 个缺口：{', '.join([g.get('crystal_id', g.get('crystal_a', '')) for g in gaps[:5]])}"
            )

        self.primitive_states["active_gap_detection"]["last_run"] = datetime.now().isoformat()
        self._write_meta_state("meta_state.json", "primitive_states", self.primitive_states)

        isolated_count = len([g for g in gaps if g.get("type") == "isolated_crystal"])
        near_dup_count = len([g for g in gaps if g.get("type") == "near_duplicate"])

        return {
            "gaps": gaps,
            "stats": {
                "total": len(gaps),
                "isolated_count": isolated_count,
                "near_dup_count": near_dup_count
            },
            "trigger_info": {
                "isolated_crystal_count": isolated_count,
                "has_isolated_crystals": isolated_count > 0
            }
        }

    def temporal_aware_escalation(self) -> List[Dict[str, Any]]:
        """
        根据时间戳和活动频率自动调整优先级

        返回：升级建议列表，并附带触发信息
        """
        if not Config.META_PRIMITIVES["temporal_aware_escalation"]["enabled"]:
            return []

        crystals = self.engine.parse_crystals()
        state = self.engine.load_layer_state()
        last_accessed = state.get("last_accessed", {})
        heat_map = state.get("heat_map", {})

        escalations = []
        today = date.today()
        stale_hot_count = 0

        for c in crystals:
            last = last_accessed.get(c.id)
            if last:
                try:
                    days_since = (today - date.fromisoformat(last)).days
                except:
                    days_since = 999
            else:
                days_since = 999

            heat = heat_map.get(c.id, 0.0)
            current_layer = state.get("layers", {}).get(c.id, "L2")

            if heat > 0.5 and days_since > 14 and current_layer == "L2":
                escalations.append({
                    "type": "stale_hot_crystal",
                    "crystal_id": c.id,
                    "heat": heat,
                    "days_since": days_since,
                    "suggestion": f"{c.id} 热度较高但 {days_since} 天未访问，建议主动召回"
                })
                stale_hot_count += 1

        self.primitive_states["temporal_aware_escalation"]["last_run"] = datetime.now().isoformat()
        self._write_meta_state("meta_state.json", "primitive_states", self.primitive_states)

        # ===== Day 3 新增：返回完整的升级信息（含统计） =====
        return {
            "escalations": escalations,
            "stats": {
                "total": len(escalations),
                "stale_hot_count": stale_hot_count
            },
            "trigger_info": {
                "stale_hot_count": stale_hot_count,
                "has_stale_hot": stale_hot_count > 0
            }
        }

    def layer_aware_calibration(self, crystals: List) -> List:
        """
        根据晶体层级调整检索权重

        返回：按层级权重调整后的晶体列表
        """
        if not Config.META_PRIMITIVES["layer_aware_calibration"]["enabled"]:
            return crystals

        state = self.engine.load_layer_state()
        layers = state.get("layers", {})

        def layer_weight(c) -> int:
            return {"L1": 3, "L2": 2, "L3": 1}.get(layers.get(c.id, "L2"), 2)

        return sorted(crystals, key=lambda c: (layer_weight(c), getattr(c, "heat", 0)), reverse=True)

    def sleep_consolidation(self) -> Dict[str, Any]:
        """
        低活跃时段自动进行知识压缩和冗余清理

        返回：巩固报告
        """
        if not Config.META_PRIMITIVES["sleep_consolidation"]["enabled"]:
            return {"status": "disabled", "message": "睡眠巩固未启用"}

        current_hour = datetime.now().hour
        start = Config.META_LAYER_CONFIG["consolidation_hour_start"]
        end = Config.META_LAYER_CONFIG["consolidation_hour_end"]

        if not (start <= current_hour < end):
            return {"status": "skipped", "message": f"当前时间 {current_hour}:00 不在巩固窗口 ({start}:00-{end}:00)"}

        crystals = self.engine.parse_crystals()
        if len(crystals) < Config.META_LAYER_CONFIG["max_crystals_before_consolidation"]:
            return {
                "status": "skipped",
                "message": f"晶体数量 {len(crystals)} 低于阈值 {Config.META_LAYER_CONFIG['max_crystals_before_consolidation']}"
            }

        archived = self.engine.archive_cold_crystals()
        gaps = self.active_gap_detection()

        result = {
            "status": "completed",
            "archived_count": len(archived),
            "gaps_found": len(gaps),
            "archived_ids": archived[:10],
            "consolidated_at": datetime.now().isoformat()
        }

        self.primitive_states["sleep_consolidation"]["last_run"] = datetime.now().isoformat()
        self._write_meta_state("meta_state.json", "primitive_states", self.primitive_states)
        return result

    def validation_gated_self_evolution(self, new_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证门控自我进化：任何自我改进必须通过验证门检验

        返回：验证结果（通过/不通过 + 原因）
        """
        if not Config.META_PRIMITIVES["validation_gated_self_evolution"]["enabled"]:
            return {"passed": True, "reason": "验证门控未启用"}

        rules = Config.META_LAYER_CONFIG["validation_gate_rules"]
        results = []

        if "new_evidence_from_at_least_3_sources" in rules:
            sources = context.get("sources", [])
            results.append({
                "rule": "new_evidence_from_at_least_3_sources",
                "passed": len(sources) >= 3,
                "reason": f"有 {len(sources)} 个来源" if len(sources) >= 3 else f"仅有 {len(sources)} 个来源，需要至少3个"
            })

        if "audit_score_gt_0.6" in rules:
            audit_score = context.get("audit_score", 0.0)
            results.append({
                "rule": "audit_score_gt_0.6",
                "passed": audit_score >= 0.6,
                "reason": f"审计评分 {audit_score:.2f} ≥ 0.6" if audit_score >= 0.6 else f"审计评分 {audit_score:.2f} 低于阈值 0.6"
            })

        if "no_major_conflict_with_existing_crystals" in rules:
            conflicts = self.engine.detect_conflicts()
            major_conflicts = [c for c in conflicts if c.similarity > 0.8]
            results.append({
                "rule": "no_major_conflict_with_existing_crystals",
                "passed": len(major_conflicts) == 0,
                "reason": "无重大冲突" if len(major_conflicts) == 0 else f"存在 {len(major_conflicts)} 个重大冲突"
            })

        all_passed = all(r["passed"] for r in results)

        self.primitive_states["validation_gated_self_evolution"]["last_run"] = datetime.now().isoformat()
        self._write_meta_state("meta_state.json", "primitive_states", self.primitive_states)

        return {
            "passed": all_passed,
            "rules": results,
            "summary": "所有验证通过" if all_passed else f"未通过：{', '.join([r['reason'] for r in results if not r['passed']])}"
        }

    def process_trigger_chains(self, primitive_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        处理元原语触发链
        检查各元原语的执行结果，根据配置的触发规则自动触发后续元原语

        Args:
            primitive_results: run_all_primitives 的返回结果

        Returns:
            触发的链列表
        """
        triggered_chains = []
        rules = Config.META_CHAIN_RULES

        # 获取各元原语的结果
        gap_result = primitive_results.get("active_gap_detection", {})
        temporal_result = primitive_results.get("temporal_aware_escalation", {})
        validation_result = primitive_results.get("validation_gated_self_evolution", {})

        # ===== 触发链1：孤立晶体 → 验证门控自我进化 =====
        chain1 = rules.get("isolated_crystal_to_validation", {})
        if chain1.get("enabled", True):
            # 检查是否满足条件：孤立晶体数量 ≥ 3
            if isinstance(gap_result, dict):
                isolated_count = gap_result.get("stats", {}).get("isolated_count", 0)
                if isolated_count >= 3:
                    # 记录触发事件
                    self.engine.log_evolution_event(
                        "chain_triggered",
                        {
                            "chain": "isolated_crystal_to_validation",
                            "source": "active_gap_detection",
                            "target": "validation_gated_self_evolution",
                            "isolated_count": isolated_count,
                            "trigger": "chain"
                        }
                    )
                    self.engine._append_change_log(
                        "元原语触发链",
                        f"主动缺口检测发现 {isolated_count} 个孤立晶体 → 触发验证门控自我进化"
                    )
                    
                    # 执行目标元原语：验证门控自我进化
                    context = {
                        "sources": [g.get("crystal_id", "") for g in gap_result.get("gaps", []) if g.get("type") == "isolated_crystal"],
                        "audit_score": 0.7,  # 模拟审计评分
                        "focus": "isolated_crystals"
                    }
                    validation_result = self.validation_gated_self_evolution({}, context)
                    
                    # 记录触发链结果
                    triggered_chains.append({
                        "chain": "isolated_crystal_to_validation",
                        "source": "active_gap_detection",
                        "target": "validation_gated_self_evolution",
                        "source_result": f"发现 {isolated_count} 个孤立晶体",
                        "target_result": validation_result.get("summary", ""),
                        "passed": validation_result.get("passed", False)
                    })
                    
                    # 更新状态
                    self.chain_states["isolated_crystal_to_validation"]["last_triggered"] = datetime.now().isoformat()
                    self.chain_states["isolated_crystal_to_validation"]["trigger_count"] += 1
                    self._write_meta_state("meta_chain_state.json", "chain_states", self.chain_states)

        # ===== 触发链2：高热度久未访问 → 主动缺口检测 =====
        chain2 = rules.get("stale_hot_to_gap_detection", {})
        if chain2.get("enabled", True):
            if isinstance(temporal_result, dict):
                stale_hot_count = temporal_result.get("stats", {}).get("stale_hot_count", 0)
                if stale_hot_count >= 2:
                    self.engine.log_evolution_event(
                        "chain_triggered",
                        {
                            "chain": "stale_hot_to_gap_detection",
                            "source": "temporal_aware_escalation",
                            "target": "active_gap_detection",
                            "stale_hot_count": stale_hot_count,
                            "trigger": "chain"
                        }
                    )
                    self.engine._append_change_log(
                        "元原语触发链",
                        f"时序感知升级发现 {stale_hot_count} 个高热度久未访问晶体 → 触发主动缺口检测"
                    )
                    
                    # 执行目标元原语：主动缺口检测（强制运行）
                    gap_result = self.active_gap_detection()
                    
                    triggered_chains.append({
                        "chain": "stale_hot_to_gap_detection",
                        "source": "temporal_aware_escalation",
                        "target": "active_gap_detection",
                        "source_result": f"发现 {stale_hot_count} 个高热度久未访问晶体",
                        "target_result": f"发现 {gap_result.get('stats', {}).get('total', 0)} 个缺口" if isinstance(gap_result, dict) else "已执行",
                        "passed": True
                    })
                    
                    self.chain_states["stale_hot_to_gap_detection"]["last_triggered"] = datetime.now().isoformat()
                    self.chain_states["stale_hot_to_gap_detection"]["trigger_count"] += 1
                    self._write_meta_state("meta_chain_state.json", "chain_states", self.chain_states)

        return triggered_chains

    # ===== Day 8: 双时间尺度进化调度 =====
    def _load_saturation_state(self) -> Dict[str, Any]:
        """加载饱和检测状态"""
        state_file = Config.DATA_ROOT / "系统日志" / "saturation_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {
            "prompt_optimization_rounds": [],
            "quality_history": [],
            "saturation_status": "unsaturated",
            "current_level": "prompt",
            "consecutive_rounds": 0,
            "last_improvement": 0.0,
            "control_logic_changes": []
        }

    def _save_saturation_state(self, state: Dict[str, Any]) -> None:
        """保存饱和检测状态"""
        state_file = Config.DATA_ROOT / "系统日志" / "saturation_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def prompt_saturation_detector(self, quality_score: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        提示词饱和检测器（含自动调温 + 回冷机制）
        检测到饱和且连续3轮时，自动 temperature += 0.2 并强制拉入百灵鸟
        连续5轮未饱和时，强制回冷至 0.7
        """
        SATURATION_THRESHOLD = 0.06
        COOLDOWN_THRESHOLD = 5
        TEMP_MAX = 1.2
        TEMP_BASELINE = 0.7

        state = self._load_saturation_state()
        context = context or {}

        modification_type = context.get("modification_type", "prompt")
        is_control_logic = context.get("is_control_logic", False)

        if is_control_logic:
            state["current_level"] = "control_logic"
            state["control_logic_changes"].append({
                "timestamp": datetime.now().isoformat(),
                "context": context,
                "quality_score": quality_score
            })
            self._save_saturation_state(state)
            return {
                "is_saturated": True,
                "consecutive_rounds": state.get("consecutive_rounds", 0),
                "improvement": state.get("last_improvement", 0.0),
                "level": "control_logic",
                "status": "escalated",
                # ===== 修复：添加缺失的字段 =====
                "avg_recent": quality_score,
                "avg_previous": quality_score,
                "temperature_adjusted": state.get("adjusted_temperature"),
                "force_lark": False
            }

        state["quality_history"].append({
            "timestamp": datetime.now().isoformat(),
            "score": quality_score,
            "type": modification_type,
            "context": context
        })

        if len(state["quality_history"]) > 20:
            state["quality_history"] = state["quality_history"][-20:]

        history = state["quality_history"]

        if len(history) < 2:
            state["saturation_status"] = "unsaturated"
            state["consecutive_rounds"] = 0
            state["last_improvement"] = 0.0
            self._save_saturation_state(state)
            return {
                "is_saturated": False,
                "consecutive_rounds": 0,
                "improvement": 0.0,
                "level": "prompt",
                "status": "unsaturated",
                "avg_recent": quality_score,
                "avg_previous": quality_score
            }

        recent_rounds = history[-5:] if len(history) >= 5 else history
        avg_recent = sum(h["score"] for h in recent_rounds) / len(recent_rounds)
        previous_slice = history[:len(history) - len(recent_rounds)]
        avg_previous = sum(h["score"] for h in previous_slice) / len(previous_slice) if previous_slice else quality_score

        saturated_count = 0
        improvements = []

        for i in range(1, len(recent_rounds)):
            current_score = recent_rounds[i]["score"]
            previous_score = recent_rounds[i - 1]["score"]
            improvement = current_score - previous_score
            improvements.append(improvement)

            if improvement > 0 and improvement < SATURATION_THRESHOLD:
                saturated_count += 1

        avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0
        is_saturated = saturated_count >= 3

        current_temp = state.get("adjusted_temperature", TEMP_BASELINE)

        if is_saturated:
            state["consecutive_rounds"] = state.get("consecutive_rounds", 0) + 1
            state["saturation_status"] = "saturated"
            state["last_improvement"] = avg_improvement

            if state["consecutive_rounds"] >= 3:
                state["current_level"] = "control_logic"

                old_temp = current_temp
                new_temp = min(TEMP_MAX, old_temp + 0.2)
                state["adjusted_temperature"] = new_temp

                self.engine._append_change_log(
                    "双时间尺度进化调度",
                    f"提示词优化已饱和（累积 {state['consecutive_rounds']} 轮），"
                    f"temperature 从 {old_temp:.1f} 调至 {new_temp:.1f}，强制拉入百灵鸟"
                )

                context["force_lark"] = True
                context["temperature_override"] = new_temp

                self.engine.log_evolution_event(
                    "saturation_auto_adjust",
                    {
                        "consecutive_rounds": state["consecutive_rounds"],
                        "old_temperature": old_temp,
                        "new_temperature": new_temp,
                        "force_lark": True,
                        "trigger": "saturation_detector"
                    }
                )

                state["consecutive_rounds"] = 0

        else:
            state["consecutive_rounds"] = max(0, state.get("consecutive_rounds", 0) - 1)
            state["saturation_status"] = "unsaturated"
            state["last_improvement"] = avg_improvement

            cooldown_counter = state.get("cooldown_counter", 0) + 1
            state["cooldown_counter"] = cooldown_counter

            if cooldown_counter >= COOLDOWN_THRESHOLD:
                old_temp = current_temp
                state["adjusted_temperature"] = TEMP_BASELINE
                state["cooldown_counter"] = 0

                self.engine._append_change_log(
                    "双时间尺度进化调度",
                    f"连续 {COOLDOWN_THRESHOLD} 轮未饱和，temperature 从 {old_temp:.1f} 回冷至 {TEMP_BASELINE:.1f}"
                )

                self.engine.log_evolution_event(
                    "saturation_cooldown",
                    {
                        "old_temperature": old_temp,
                        "new_temperature": TEMP_BASELINE,
                        "cooldown_threshold": COOLDOWN_THRESHOLD,
                        "trigger": "cooldown_mechanism"
                    }
                )
            else:
                if state.get("adjusted_temperature", TEMP_BASELINE) > TEMP_BASELINE:
                    new_temp = max(TEMP_BASELINE, state["adjusted_temperature"] - 0.1)
                    state["adjusted_temperature"] = new_temp

        self._save_saturation_state(state)

        return {
            "is_saturated": is_saturated,
            "consecutive_rounds": state.get("consecutive_rounds", 0),
            "improvement": round(avg_improvement, 3),
            "level": state.get("current_level", "prompt"),
            "status": state.get("saturation_status", "unsaturated"),
            "saturated_count": saturated_count,
            "avg_recent": round(avg_recent, 3),
            "avg_previous": round(avg_previous, 3),
            "temperature_adjusted": state.get("adjusted_temperature", None),
            "force_lark": context.get("force_lark", False),
            "cooldown_counter": state.get("cooldown_counter", 0)
        }

    def get_saturation_status(self) -> Dict[str, Any]:
        """获取当前饱和状态"""
        state = self._load_saturation_state()
        return {
            "saturation_status": state.get("saturation_status", "unsaturated"),
            "current_level": state.get("current_level", "prompt"),
            "consecutive_rounds": state.get("consecutive_rounds", 0),
            "last_improvement": state.get("last_improvement", 0.0),
            "quality_history_count": len(state.get("quality_history", [])),
            "control_logic_changes_count": len(state.get("control_logic_changes", []))
        }

    def diagnose_failure_patterns(self) -> Dict[str, Any]:
        """
        识别历史中的失败模式。

        分析 evolution_log.json 中的事件，识别重复出现的失败模式，
        生成预防性建议。

        Returns:
            dict: 分析结果
                - patterns (List[Dict]): 发现的模式列表
                - summary (str): 摘要
                - recommendations (List[str]): 改进建议
                - total_events (int): 分析的事件总数
                - analysis_timestamp (str): 分析时间戳
        """
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        if not log_path.exists():
            return {
                "patterns": [],
                "summary": "进化日志文件不存在，无法分析",
                "recommendations": ["请先运行系统，积累一些数据"],
                "total_events": 0,
                "analysis_timestamp": datetime.now().isoformat()
            }

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            return {
                "patterns": [],
                "summary": "进化日志文件损坏，无法分析",
                "recommendations": ["请检查 evolution_log.json 文件"],
                "total_events": 0,
                "analysis_timestamp": datetime.now().isoformat()
            }

        events = data.get("events", [])
        if not events:
            return {
                "patterns": [],
                "summary": "进化日志为空，暂无数据",
                "recommendations": ["请继续使用系统积累数据"],
                "total_events": 0,
                "analysis_timestamp": datetime.now().isoformat()
            }

        # ===== 调试：打印实际事件类型 =====
        import json as json_module
        print("=" * 60)
        print("📊 evolution_log.json 事件类型统计")
        print("=" * 60)
        event_types = {}
        for event in events:
            et = event.get("event_type", "unknown")
            event_types[et] = event_types.get(et, 0) + 1
        for et, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {et}: {count} 次")

        # 打印前3个事件的完整结构
        print("\n📋 前3个事件示例:")
        for i, event in enumerate(events[:3]):
            print(f"\n事件 {i+1}:")
            print(json_module.dumps(event, ensure_ascii=False, indent=2)[:800])

        print("=" * 60)

        # ===== 分析失败模式 =====
        patterns = []
        recommendations = []

        # 1. 分析晶体引用不足模式
        low_ref_events = []
        for event in events:
            if event.get("event_type") == "alarm":
                details = event.get("details", {})
                if details.get("rule") == "knowledge_poverty":
                    low_ref_events.append(event)

        if len(low_ref_events) >= 2:
            is_consecutive = self._check_consecutive_events(events, "alarm", "knowledge_poverty", 2)
            severity = "高" if is_consecutive else "中"
            patterns.append({
                "type": "crystal_reference_insufficient",
                "name": "晶体引用不足",
                "count": len(low_ref_events),
                "consecutive": is_consecutive,
                "severity": severity,
                "description": f"历史中共出现 {len(low_ref_events)} 次晶体引用不足警报"
            })
            recommendations.append(
                f"建议在辩论前强制加载至少 2 条相关晶体（发生 {len(low_ref_events)} 次）"
            )

        # 2. 分析思维固化模式
        stagnation_events = []
        for event in events:
            if event.get("event_type") == "alarm":
                details = event.get("details", {})
                if details.get("rule") == "thought_stagnation":
                    stagnation_events.append(event)

        if len(stagnation_events) >= 2:
            is_consecutive = self._check_consecutive_events(events, "alarm", "thought_stagnation", 2)
            severity = "高" if is_consecutive else "中"
            patterns.append({
                "type": "thought_stagnation",
                "name": "思维固化",
                "count": len(stagnation_events),
                "consecutive": is_consecutive,
                "severity": severity,
                "description": f"历史中共出现 {len(stagnation_events)} 次思维固化警报"
            })
            recommendations.append(
                f"建议在辩论中增加奇谋者或激进者角色（发生 {len(stagnation_events)} 次）"
            )

        # 3. 分析验证失败模式
        verification_failures = []
        for event in events:
            if event.get("event_type") == "verification_passed":
                details = event.get("details", {})
                rules_passed = details.get("rules_passed", 0)
                rules_total = details.get("rules_total", 4)
                if rules_passed < rules_total * 0.5:
                    verification_failures.append(event)

        if len(verification_failures) >= 2:
            patterns.append({
                "type": "verification_failed",
                "name": "验证门控失败",
                "count": len(verification_failures),
                "consecutive": False,
                "severity": "中",
                "description": f"历史中共出现 {len(verification_failures)} 次验证通过率低于50%"
            })
            recommendations.append(
                f"建议检查晶体质量标准和验证规则（失败 {len(verification_failures)} 次）"
            )

        # 4. 分析无晶体引用模式
        no_ref_events = []
        for event in events:
            if event.get("event_type") == "alarm":
                details = event.get("details", {})
                data = details.get("data", {})
                if data.get("ref_rate", 1.0) == 0:
                    no_ref_events.append(event)

        if len(no_ref_events) >= 1:
            patterns.append({
                "type": "zero_crystal_reference",
                "name": "完全无晶体引用",
                "count": len(no_ref_events),
                "consecutive": False,
                "severity": "高",
                "description": f"历史中共出现 {len(no_ref_events)} 次完全无晶体引用"
            })
            recommendations.append(
                "建议在辩论前强制加载至少 1 条晶体作为初始种子"
            )

        # 5. 分析 Hebbian 学习趋势
        hebbian_events = []
        for event in events:
            if "Hebbian" in event.get("event_type", "") or "hebbian" in event.get("event_type", "").lower():
                hebbian_events.append(event)

        if len(hebbian_events) >= 3:
            patterns.append({
                "type": "hebbian_active",
                "name": "Hebbian学习活跃",
                "count": len(hebbian_events),
                "consecutive": False,
                "severity": "低",
                "description": f"历史中共有 {len(hebbian_events)} 次 Hebbian 学习更新"
            })

        # 6. 分析未归档孔洞模式
        deposit_events = []
        for event in events:
            if event.get("event_type") == "deposit_unarchived_holes":
                deposit_events.append(event)

        if len(deposit_events) >= 2:
            patterns.append({
                "type": "unarchived_holes",
                "name": "未归档孔洞",
                "count": len(deposit_events),
                "consecutive": False,
                "severity": "中",
                "description": f"历史中有 {len(deposit_events)} 次辩论产生了未归档的 L3 孔洞"
            })
            recommendations.append(
                f"建议在辩论结束后主动检查并归档 L3 孔洞（出现 {len(deposit_events)} 次）"
            )

        # 7. 分析沉思式反思事件
        contemplation_events = []
        for event in events:
            if event.get("event_type") == "contemplative_reflection":
                contemplation_events.append(event)

        if len(contemplation_events) >= 3:
            patterns.append({
                "type": "contemplation_active",
                "name": "沉思式反思活跃",
                "count": len(contemplation_events),
                "consecutive": False,
                "severity": "低",
                "description": f"历史中共有 {len(contemplation_events)} 次沉思式反思"
            })

        # 生成综合摘要
        if patterns:
            summary = f"识别到 {len(patterns)} 种模式，共 {sum(p['count'] for p in patterns)} 次事件"
            if len(recommendations) > 0:
                summary += f"，建议: {recommendations[0]}"
        else:
            if len(events) > 50:
                summary = f"系统运行良好，但事件数较多（{len(events)} 条），建议关注高频事件类型"
                recommendations = ["建议查看具体事件类型，关注异常模式"]
            else:
                summary = "未识别到明显的失败模式，系统运行良好"

        return {
            "patterns": patterns,
            "summary": summary,
            "recommendations": recommendations if recommendations else ["系统运行良好，暂无预防性建议"],
            "total_events": len(events),
            "analysis_timestamp": datetime.now().isoformat()
        }

    def _check_consecutive_events(self, events: List[Dict], event_type: str, rule: str, threshold: int = 2) -> bool:
        """
        检查是否存在连续的同类型事件
        """
        consecutive_count = 0
        for event in events:
            if event.get("event_type") == event_type:
                details = event.get("details", {})
                if details.get("rule") == rule:
                    consecutive_count += 1
                    if consecutive_count >= threshold:
                        return True
                else:
                    consecutive_count = 0
            else:
                consecutive_count = 0
        return False

    def get_evolution_stats_enhanced(self) -> Dict[str, Any]:
        """
        增强版进化统计（包含失败模式分析）
        """
        base_stats = self.get_evolution_stats()
        failure_patterns = self.diagnose_failure_patterns()

        return {
            **base_stats,
            "failure_patterns": failure_patterns,
            "version": "2.0"
        }

    # ===== Day 8: 灵感熔炉复盘（一） =====
    def inspiration_furnace_review(self) -> Dict[str, Any]:
        """
        灵感熔炉复盘（一）

        从灵感池.json中读取状态为"待筛选"的记录，
        运行L2筛选（重要性、紧急性、与主线目标的一致性、资源投入估算），
        产出"待采纳清单"
        """
        insp_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
        if not insp_path.exists():
            return {
                "total_pending": 0,
                "s_level": [],
                "a_level": [],
                "b_level": [],
                "rejected": [],
                "summary": "灵感池文件不存在"
            }

        try:
            with open(insp_path, "r", encoding="utf-8") as f:
                inspirations = json.load(f)
        except:
            return {
                "total_pending": 0,
                "s_level": [],
                "a_level": [],
                "b_level": [],
                "rejected": [],
                "summary": "灵感池文件解析失败"
            }

        # 筛选"待筛选"状态的灵感
        pending = [i for i in inspirations if i.get("status") == "待筛选"]

        if not pending:
            return {
                "total_pending": 0,
                "s_level": [],
                "a_level": [],
                "b_level": [],
                "rejected": [],
                "summary": "暂无待筛选的灵感"
            }

        # L2筛选：评估每个灵感
        s_level = []
        a_level = []
        b_level = []
        rejected = []

        for insp in pending:
            content = insp.get("content", "")

            # 评估指标
            importance_score = self._evaluate_importance(content)
            urgency_score = self._evaluate_urgency(content)
            alignment_score = self._evaluate_alignment(content)
            resource_estimate = self._estimate_resources(content)

            # 综合评分
            total_score = (importance_score * 0.5 + urgency_score * 0.2 + alignment_score * 0.3)

            # 调试日志（在GUI中显示）
            self.engine._append_change_log(
                "灵感评估",
                f"{insp.get('id')}: 重要性={importance_score:.2f}, 紧急性={urgency_score:.2f}, "
                f"一致性={alignment_score:.2f}, 资源={resource_estimate}h, 总分={total_score:.2f}"
            )

            # 分类
            if total_score >= 0.65 and resource_estimate <= 3:
                insp["evaluation"] = {
                    "importance": importance_score,
                    "urgency": urgency_score,
                    "alignment": alignment_score,
                    "resource_hours": resource_estimate,
                    "total_score": total_score,
                    "level": "S"
                }
                s_level.append(insp)
            elif total_score >= 0.5 and resource_estimate <= 6:
                insp["evaluation"] = {
                    "importance": importance_score,
                    "urgency": urgency_score,
                    "alignment": alignment_score,
                    "resource_hours": resource_estimate,
                    "total_score": total_score,
                    "level": "A"
                }
                a_level.append(insp)
            elif total_score >= 0.35 and resource_estimate <= 16:
                insp["evaluation"] = {
                    "importance": importance_score,
                    "urgency": urgency_score,
                    "alignment": alignment_score,
                    "resource_hours": resource_estimate,
                    "total_score": total_score,
                    "level": "B"
                }
                b_level.append(insp)
            else:
                insp["evaluation"] = {
                    "importance": importance_score,
                    "urgency": urgency_score,
                    "alignment": alignment_score,
                    "resource_hours": resource_estimate,
                    "total_score": total_score,
                    "level": "rejected"
                }
                rejected.append(insp)

        # 更新灵感池状态
        updated_inspirations = []
        for insp in inspirations:
            if insp.get("status") == "待筛选":
                # 检查是否在已分类列表中
                classified = None
                for item in s_level + a_level + b_level + rejected:
                    if item.get("id") == insp.get("id"):
                        classified = item
                        break
                if classified:
                    # 更新状态
                    classified["status"] = "已评估"
                    updated_inspirations.append(classified)
                else:
                    updated_inspirations.append(insp)
            else:
                updated_inspirations.append(insp)

        with open(insp_path, "w", encoding="utf-8") as f:
            json.dump(updated_inspirations, f, ensure_ascii=False, indent=2)

        # 记录到进化日志
        self.engine.log_evolution_event(
            "inspiration_review",
            {
                "total_pending": len(pending),
                "s_level_count": len(s_level),
                "a_level_count": len(a_level),
                "b_level_count": len(b_level),
                "rejected_count": len(rejected),
                "trigger": "day8_review"
            }
        )

        summary = (
            f"灵感熔炉复盘（一）完成：\n"
            f"  - S级（<3小时）：{len(s_level)} 条\n"
            f"  - A级（半天内）：{len(a_level)} 条\n"
            f"  - B级（1-2天）：{len(b_level)} 条\n"
            f"  - 已拒绝：{len(rejected)} 条"
        )

        return {
            "total_pending": len(pending),
            "s_level": s_level,
            "a_level": a_level,
            "b_level": b_level,
            "rejected": rejected,
            "summary": summary
        }
    # ===== Day 22: 灵感熔炉复盘（二） =====
    def inspiration_furnace_review_phase2(self) -> Dict[str, Any]:
        """
        灵感熔炉复盘（二）：
        1. 处理新产生的“待筛选”灵感（复用一阶段的筛选逻辑）。
        2. 对 S/A 级灵感自动执行（生成晶体或任务卡片）。
        3. 对已执行的灵感补充闭环反馈。
        4. 记录 S/A 级执行事件到进化日志。
        5. 生成中期报告。
        """
        # ---- 1. 先处理待筛选的新灵感（调用一阶段逻辑） ----
        first_result = self.inspiration_furnace_review()
        self.engine._append_change_log(
            "灵感熔炉复盘（二）",
            f"一阶段复盘完成，处理待筛选灵感 {first_result.get('total_pending', 0)} 条"
        )

        # ---- 2. 读取灵感池 ----
        insp_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
        if not insp_path.exists():
            return {"error": "灵感池文件不存在"}

        try:
            with open(insp_path, "r", encoding="utf-8") as f:
                inspirations = json.load(f)
        except:
            return {"error": "灵感池文件解析失败"}

        # ---- 3. 处理 S/A 级灵感的自动执行 ----
        executed_ids = []
        for insp in inspirations:
            status = insp.get("status")
            if status != "已评估":
                continue
            eval_data = insp.get("evaluation", {})
            level = eval_data.get("level", "")
            if level not in ("S", "A"):
                continue

            # 检查是否已经执行过（可能已手动执行）
            if "result" in insp:
                continue

            # 自动执行：S级 -> 直接晶体化；A级 -> 生成任务卡片
            if level == "S":
                result = self._execute_inspiration(insp, target="crystal")
            else:
                result = self._execute_inspiration(insp, target="task")

            if result.get("success"):
                insp["status"] = "已执行"
                insp["result"] = result
                insp["executed_at"] = datetime.now().isoformat()
                executed_ids.append(insp["id"])
                # 记录到进化日志
                self.engine.log_evolution_event(
                    "inspiration_executed",
                    {
                        "inspiration_id": insp["id"],
                        "level": level,
                        "target": result.get("target_id"),
                        "result": result.get("message"),
                        "trigger": "phase2_auto_execute"
                    }
                )

        # ---- 4. 处理已执行但缺少闭环反馈的记录 ----
        for insp in inspirations:
            if insp.get("status") == "已执行" and "result" in insp:
                # 如果 result 中没有 feedback 字段，补充一个简单的反馈
                if "feedback" not in insp["result"]:
                    # 这里可以根据实际效果评估，简化为“自动标记成功”
                    insp["result"]["feedback"] = "已自动执行，尚未验证效果。"

        # ---- 5. 保存更新后的灵感池 ----
        with open(insp_path, "w", encoding="utf-8") as f:
            json.dump(inspirations, f, ensure_ascii=False, indent=2)

        # ---- 6. 生成中期报告 ----
        report = self._generate_inspiration_midterm_report(inspirations)

        # 将报告存入文件
        report_path = Config.DATA_ROOT / "系统日志" / "灵感熔炉中期报告.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.engine._append_change_log(
            "灵感熔炉复盘（二）",
            f"中期报告已生成，执行了 {len(executed_ids)} 条 S/A 级灵感"
        )

        return {
            "status": "success",
            "executed_count": len(executed_ids),
            "report": report,
            "report_path": str(report_path)
        }

    def _execute_inspiration(self, insp: Dict, target: str = "crystal") -> Dict:
        """
        执行单条灵感：转化为晶体或任务卡片。
        """
        content = insp.get("content", "")
        if not content:
            return {"success": False, "message": "灵感内容为空"}

        if target == "crystal":
            # 使用 CrystalEngine 创建晶体
            # 生成新 ID
            crystals = self.engine.parse_crystals()
            max_num = max([int(c.id.replace("C", "")) for c in crystals], default=0)
            new_id = f"C{max_num + 1:03d}"
            success = self.engine.create_crystal(
                crystal_id=new_id,
                content=content[:80],
                links=[],
                source="inspiration_phase2"
            )
            if success:
                return {"success": True, "target_id": new_id, "message": f"已生成晶体 {new_id}"}
            else:
                return {"success": False, "message": "晶体创建失败"}

        elif target == "task":
            # 生成任务卡片（存入 PENDING 或 task_cards）
            from dataclasses import asdict
            card_id = f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hash(content) % 1000:03d}"
            task = TaskCard(
                id=card_id,
                type="inspiration",
                title=f"灵感执行：{content[:30]}",
                content=content,
                source="灵感熔炉",
                suggested_action="请确认并执行",
                status="pending"
            )
            cards = self.engine._load_task_cards()  # 需要访问 engine 的私有方法，这里用 self.engine
            # 但 _load_task_cards 是 CrystalEngine 的方法，直接调用
            cards = self.engine._load_task_cards()
            cards.append(asdict(task))
            self.engine._save_task_cards(cards)
            return {"success": True, "target_id": card_id, "message": f"已生成任务卡片 {card_id}"}

        return {"success": False, "message": "未知目标类型"}

    def _generate_inspiration_midterm_report(self, inspirations: List[Dict]) -> Dict:
        """
        生成灵感熔炉中期报告。
        """
        total = len(inspirations)
        status_count = {"待筛选": 0, "已评估": 0, "已执行": 0, "已拒绝": 0}
        level_count = {"S": 0, "A": 0, "B": 0, "rejected": 0}
        executed_with_result = 0

        for insp in inspirations:
            status = insp.get("status", "未知")
            status_count[status] = status_count.get(status, 0) + 1
            eval_data = insp.get("evaluation", {})
            level = eval_data.get("level", "")
            if level in level_count:
                level_count[level] += 1
            if status == "已执行" and "result" in insp:
                executed_with_result += 1

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_inspirations": total,
            "status_distribution": status_count,
            "level_distribution": level_count,
            "executed_with_feedback": executed_with_result,
            "execution_success_rate": executed_with_result / status_count.get("已执行", 1) if status_count.get("已执行", 0) > 0 else 0,
            "summary": f"共 {total} 条灵感，已执行 {status_count.get('已执行', 0)} 条，其中 {executed_with_result} 条已闭环。"
        }
        return report
    
    def _evaluate_importance(self, content: str) -> float:
        """评估灵感的重要性（0-1）"""
        high_importance = ["核心", "关键", "突破", "创新", "战略", "架构", "系统", "框架", "机制", "范式"]
        medium_importance = ["优化", "改进", "增强", "提升", "完善", "调整", "补充"]

        content_lower = content.lower()
        high_score = sum(0.3 for kw in high_importance if kw in content_lower)
        medium_score = sum(0.15 for kw in medium_importance if kw in content_lower)

        # 长度加成（更长的描述通常更具体）
        length_bonus = min(0.2, len(content) / 500)

        return min(1.0, high_score + medium_score + length_bonus)

    def _evaluate_urgency(self, content: str) -> float:
        """评估灵感的紧急性（0-1）"""
        urgent_keywords = ["紧急", "立刻", "马上", "尽快", "亟待", "急需", "关键", "阻塞", "阻断"]
        content_lower = content.lower()
        score = sum(0.25 for kw in urgent_keywords if kw in content_lower)
        return min(1.0, score)

    def _evaluate_alignment(self, content: str) -> float:
        """评估灵感与主线目标的一致性（0-1）"""
        # 主线目标关键词
        main_keywords = ["晶体", "认知", "辩论", "决策", "八道防线", "沉思", "进化", "学习", "智能", "知识"]
        content_lower = content.lower()
        score = sum(0.15 for kw in main_keywords if kw in content_lower)
        return min(1.0, score + 0.2)  # 基础分0.2

    def _estimate_resources(self, content: str) -> int:
        """估算资源投入（小时）"""
        # 基于内容长度和复杂度估算
        length = len(content)

        if length < 50:
            return 1  # 简单想法，1小时
        elif length < 150:
            return 2  # 中等想法，2小时
        elif length < 300:
            return 4  # 复杂想法，半天
        else:
            # 检查是否有"实现"、"构建"等关键词
            if "实现" in content or "构建" in content or "开发" in content:
                return 8  # 需要实现，1天
            return 4  # 默认半天

    def diagnose_history(self, question: str, threshold: float = 0.7) -> Dict[str, Any]:
        """
        历史诊断与经验复用（非马尔可夫历史检索）。

        从 evolution_log.json 中检索历史失败轨迹和成功经验，
        匹配当前问题与历史问题，返回最相似的历史记录及其有效晶体组合。

        Args:
            question (str): 当前问题
            threshold (float, optional): 相似度阈值 (0-1)，默认 0.7

        Returns:
            dict: 匹配结果
                - matched (bool): 是否找到有效匹配
                - match_score (float): 最佳匹配相似度
                - reused_history_id (str): 复用的历史记录ID
                - crystal_combination (List[str]): 该历史问题对应的有效晶体组合
                - diagnosis (str): 历史诊断结论
                - repair_attempts (List[Dict]): 历史修复尝试
        """
        log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
        if not log_path.exists():
            return {
                "matched": False,
                "match_score": 0.0,
                "reused_history_id": None,
                "crystal_combination": [],
                "diagnosis": "",
                "repair_attempts": []
            }

        # 读取日志
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            return {
                "matched": False,
                "match_score": 0.0,
                "reused_history_id": None,
                "crystal_combination": [],
                "diagnosis": "",
                "repair_attempts": []
            }

        events = data.get("events", [])
        if not events:
            return {
                "matched": False,
                "match_score": 0.0,
                "reused_history_id": None,
                "crystal_combination": [],
                "diagnosis": "",
                "repair_attempts": []
            }

        # 1. 筛选有失败轨迹或诊断信息的事件
        candidate_events = []
        for event in events:
            # 检查是否有失败轨迹
            if "failure_traces" in event or "diagnosis" in event:
                # 尝试从 details 中提取问题原文
                details = event.get("details", {})
                history_question = details.get("question", "") or details.get("user_input", "")
                if history_question:
                    candidate_events.append({
                        "event": event,
                        "question": history_question,
                        "timestamp": event.get("timestamp", "")
                    })
            # 也检查是否有成功复用的历史（用于正向强化）
            if event.get("event_type") == "history_reused":
                details = event.get("details", {})
                history_question = details.get("question", "")
                if history_question:
                    candidate_events.append({
                        "event": event,
                        "question": history_question,
                        "timestamp": event.get("timestamp", "")
                    })

        if not candidate_events:
            return {
                "matched": False,
                "match_score": 0.0,
                "reused_history_id": None,
                "crystal_combination": [],
                "diagnosis": "",
                "repair_attempts": []
            }

        # 2. 计算当前问题与每个历史问题的相似度
        scored = []
        for item in candidate_events:
            sim = self.engine._simple_similarity(question, item["question"])
            scored.append({
                **item,
                "similarity": sim
            })

        # 3. 按相似度降序排序
        scored.sort(key=lambda x: x["similarity"], reverse=True)

        # 4. 选择最佳匹配
        best = scored[0]
        if best["similarity"] >= threshold:
            event = best["event"]
            details = event.get("details", {})
            
            # 提取有效晶体组合
            crystal_combination = []
            # 从 repair_attempts 中提取成功方案中使用的晶体
            repair_attempts = event.get("repair_attempts", [])
            for attempt in repair_attempts:
                if attempt.get("success", False):
                    crystal_combination.extend(attempt.get("crystals_used", []))
            # 如果 repair_attempts 中没有，尝试从 details 中提取
            if not crystal_combination:
                crystal_combination = details.get("effective_crystals", [])

            return {
                "matched": True,
                "match_score": best["similarity"],
                "reused_history_id": event.get("timestamp", ""),
                "crystal_combination": list(set(crystal_combination)),  # 去重
                "diagnosis": event.get("diagnosis", details.get("diagnosis", "")),
                "repair_attempts": repair_attempts,
                "matched_question": best["question"]
            }
        else:
            return {
                "matched": False,
                "match_score": best["similarity"],
                "reused_history_id": None,
                "crystal_combination": [],
                "diagnosis": "",
                "repair_attempts": []
            }

    def run_all_primitives(self) -> Dict[str, Any]:
        """
        运行所有已启用的元原语，并处理触发链
        """
        # 1. 运行各元原语
        results = {
            "active_gap_detection": self.active_gap_detection(),
            "temporal_aware_escalation": self.temporal_aware_escalation(),
            "sleep_consolidation": self.sleep_consolidation(),
            "validation_gated_self_evolution": {
                "status": "pending",
                "message": "在晶体更新时调用，需传入 new_data 和 context 参数"
            }
        }

        # 2. Day 3 新增：处理触发链
        triggered = self.process_trigger_chains(results)
        results["triggered_chains"] = triggered

        # 3. 记录触发链日志
        if triggered:
            for chain in triggered:
                self.engine._append_change_log(
                    "触发链执行",
                    f"{chain['chain']}: {chain['source']} → {chain['target']} (通过: {chain['passed']})"
                )
        # ===== Day 11: 运行定时探索调度 =====
        try:
            self._log("🔍 运行定时探索调度检查...", "system")
            exploration_result = self.force_explorer.run_scheduled_exploration()
            results["force_exploration"] = exploration_result
            if exploration_result.get("processed", 0) > 0:
                self._log(f"✅ 强制探索完成: 处理 {exploration_result['processed']} 个孔洞", "success")
        except Exception as e:
            self._log(f"⚠️ 定时探索调度失败: {e}", "warning")
            results["force_exploration"] = {"error": str(e)}

        # ===== 双环：stage -> fast -> execute -> slow -> verify =====
        try:
            self._log("🔄 双环执行器启动...", "system")
            results["dual_loop"] = self.run_dual_loop()
        except Exception as e:
            self._log(f"⚠️ 双环执行失败：{e}", "warning")
            results["dual_loop"] = {"error": str(e)}

        return results

    def run_dual_loop(self, max_merges: int = 2, max_grafts: int = 1) -> Dict[str, Any]:
        """运行可执行双环：冲突合并/灵感嫁接 → 快环筛选 → 执行 → 慢环判定回滚 → 双环验证。"""
        from evolution.dual_loop import DualLoopRunner

        runner = DualLoopRunner(self.engine, log_callback=self._log)
        result = runner.run_once(max_merges=max_merges, max_grafts=max_grafts)
        self._log(
            f"🔄 双环执行完成：执行 {result.get('executed', 0)}，回滚 {result.get('rolled_back', 0)}，"
            f"跳过 {result.get('skipped', 0)}",
            "system",
        )
        return result

    # ========================================================================
    # Day 17: 反诈三模块
    # ========================================================================

    def run_anti_fraud_audit(self, context: Dict = None) -> Dict[str, Any]:
        """
        运行反诈三模块审计

        在"双环闭环验证"的"外环审计"中嵌入三个反诈审计模块

        Args:
            context: 审计上下文（包含对话、IP、文本等）

        Returns:
            Dict: 审计结果，包含三个模块的检测记录
        """
        context = context or {}
        results = {
            "persona_detection": {"passed": True, "records": []},
            "starlink_fingerprint": {"passed": True, "records": []},
            "cross_lingual": {"passed": True, "records": []},
            "overall_passed": True,
            "timestamp": datetime.now().isoformat()
        }

        # 1. AI人设检测器
        try:
            dialogue = context.get("dialogue", "")
            if dialogue:
                if self.anti_fraud_providers is None:
                    results["persona_detection"] = {
                        "passed": False,
                        "error": "anti_fraud_providers 未注入",
                    }
                else:
                    detector = self.anti_fraud_providers.AIPersonaDetector()
                    persona_result = detector.detect(dialogue)
                    results["persona_detection"] = persona_result
        except Exception as e:
            results["persona_detection"]["error"] = str(e)

        # 2. 星链信号指纹库
        try:
            ip = context.get("ip", "")
            if ip:
                if self.anti_fraud_providers is None:
                    results["starlink_fingerprint"] = {
                        "passed": False,
                        "error": "anti_fraud_providers 未注入",
                    }
                else:
                    starlink = self.anti_fraud_providers.StarlinkFingerprintDB()
                    starlink_result = starlink.check(ip)
                    results["starlink_fingerprint"] = starlink_result
        except Exception as e:
            results["starlink_fingerprint"]["error"] = str(e)

        # 3. 跨语言语义一致性审计
        try:
            text_zh = context.get("text_zh", "")
            text_en = context.get("text_en", "")
            if text_zh and text_en:
                if self.anti_fraud_providers is None:
                    results["cross_lingual"] = {
                        "passed": False,
                        "error": "anti_fraud_providers 未注入",
                    }
                else:
                    auditor = self.anti_fraud_providers.CrossLingualAuditor(
                        self.ai_client
                    )
                    lingual_result = auditor.audit(text_zh, text_en)
                    results["cross_lingual"] = lingual_result
        except Exception as e:
            results["cross_lingual"]["error"] = str(e)

        # 总体判断
        results["overall_passed"] = (
            results["persona_detection"].get("passed", True) and
            results["starlink_fingerprint"].get("passed", True) and
            results["cross_lingual"].get("passed", True)
        )

        # 记录到进化日志
        if not results["overall_passed"]:
            self.engine.log_evolution_event(
                "anti_fraud_alert",
                {
                    "persona_risk": not results["persona_detection"].get("passed", True),
                    "starlink_risk": not results["starlink_fingerprint"].get("passed", True),
                    "lingual_risk": not results["cross_lingual"].get("passed", True),
                    "trigger": "dual_loop_audit"
                }
            )

        return results
   
    def trigger_gödel_evolution(self, role_name: str = "radical") -> Dict[str, Any]:
        """
        触发 Gödel Agent 进化循环
        
        Args:
            role_name: 要改进的角色名称
        
        Returns:
            Dict: 进化结果
        """
        if not self.ai_client:
            return {"error": "AI Client 未配置，无法执行进化"}
        
        self._log(f"🧠 启动 Gödel Agent 进化循环（角色: {role_name}）", "system")
        
        try:
            result = self.gödel_agent.run_evolution_cycle(role_name)
            
            if result.get("applied", False):
                self._log(f"✅ Gödel Agent 应用了 {role_name} 的 Prompt 改进", "success")
                self.engine._append_change_log(
                    "Gödel Agent 进化",
                    f"角色 {role_name} 的 Prompt 已升级到新版本"
                )
            else:
                self._log("ℹ️ Gödel Agent 未找到有效的改进候选", "system")
            
            return result
        except Exception as e:
            self._log(f"❌ Gödel Agent 进化失败: {e}", "error")
            return {"error": str(e)}
    
    def get_gödel_status(self) -> Dict[str, Any]:
        """获取 Gödel Agent 状态"""
        return self.gödel_agent.get_evolution_status()
    
    def get_prompt_templates(self) -> Dict[str, PromptTemplate]:
        """获取所有 Prompt 模板"""
        return self.template_manager.get_all_templates()
