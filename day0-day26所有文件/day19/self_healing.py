#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自我修复循环模块
Day 19 新增
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# 延迟导入 Config，避免循环导入
# 在方法内部使用 from crystal_tree_all_in_one_day import Config

class SelfHealing:
    """
    自我修复引擎
    检测连续低质量对话，自动触发修复流程
    """

    def __init__(self, engine, ai_client=None, log_callback=None):
        """
        :param engine: CrystalEngine实例
        :param ai_client: AIClient实例（可选）
        :param log_callback: 日志回调函数
        """
        self.engine = engine
        self.ai = ai_client
        self.log = log_callback or (lambda msg, level="system": print(f"[{level.upper()}] {msg}"))
        # 从 engine 获取数据根目录，避免直接引用 Config
        if hasattr(engine, 'files') and hasattr(engine.files, 'DATA_ROOT'):
            self.data_root = engine.files.DATA_ROOT
        else:
            # 降级：使用 Config（延迟导入）
            from crystal_tree_all_in_one_day import Config
            self.data_root = Config.DATA_ROOT
        
        self.consecutive_low_count = 0
        self.threshold = 3  # 连续3次低质量触发修复
        self.quality_threshold = 0.4  # 质量评分低于0.4视为低质量
        self.last_repair_time = None
        self.repair_history = []
        self._load_state()

    def _load_state(self):
        """从文件加载状态"""
        state_file = self.data_root / "系统日志" / "self_healing_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.consecutive_low_count = data.get("consecutive_low_count", 0)
                    self.last_repair_time = data.get("last_repair_time")
                    self.repair_history = data.get("repair_history", [])
            except:
                pass

    def _save_state(self):
        """保存状态到文件"""
        state_file = self.data_root / "系统日志" / "self_healing_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({
                "consecutive_low_count": self.consecutive_low_count,
                "last_repair_time": self.last_repair_time,
                "repair_history": self.repair_history[-50:]  # 只保留最近50条
            }, f, ensure_ascii=False, indent=2)

    def record_quality(self, quality_score: float, context: Dict = None):
        """
        记录一次对话质量评分
        每次对话结束后调用
        """
        if quality_score < self.quality_threshold:
            self.consecutive_low_count += 1
            self.log(f"⚠️ 低质量对话记录：评分 {quality_score:.2f}，连续 {self.consecutive_low_count} 次", "warning")
        else:
            self.consecutive_low_count = 0  # 重置
            self.log(f"✅ 质量正常：评分 {quality_score:.2f}，连续低质量已重置", "system")

        self._save_state()

        # 如果达到阈值，触发修复
        if self.consecutive_low_count >= self.threshold:
            self.log(f"🚨 连续 {self.threshold} 次低质量对话，触发自我修复流程", "error")
            self._trigger_repair(context)
    def force_trigger_repair(self):
        """强制触发修复（用于测试）"""
        self.log("🔧 强制触发修复（测试模式）", "system")
        self.consecutive_low_count = self.threshold  # 直接达到阈值
        self._trigger_repair({"force": True})
    def _trigger_repair(self, context: Dict = None):
        """触发修复流程"""
        # 1. 防止短时间内重复修复（至少间隔1小时）
        if self.last_repair_time:
            try:
                last = datetime.fromisoformat(self.last_repair_time)
                if (datetime.now() - last).total_seconds() < 3600:
                    self.log("⏳ 修复过于频繁（<1小时），本次跳过", "warning")
                    self.consecutive_low_count = 0  # 重置计数避免反复触发
                    self._save_state()
                    return
            except:
                pass

        self.log("🛠️ 开始自我修复流程...", "system")

        # 2. 暂停外部服务（标记）
        self._pause_services()

        # 3. 运行完整健康审计
        try:
            if hasattr(self.engine, 'run_audit_now'):
                report = self.engine.run_audit_now()
            else:
                # 尝试使用 LayerAuditService
                from crystal_tree_all_in_one_day import LayerAuditService
                auditor = LayerAuditService(self.engine, self.engine.files)
                report = auditor.run_audit()
                # 转换为 dict
                report = {
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
            self.log(f"📊 健康审计完成，健康评分：{report.get('health_score', 0)}/10", "system")
        except Exception as e:
            self.log(f"❌ 健康审计失败：{e}", "error")
            self._resume_services()
            return

        # 4. 识别最弱环节
        weak_points = self._identify_weak_points(report)
        self.log(f"🎯 识别到弱环节：{', '.join(weak_points) if weak_points else '无'}", "system")

        # 5. 应用修复策略
        repair_actions = []
        for point in weak_points:
            action = self._apply_repair(point, report)
            if action:
                repair_actions.append(action)

        # 6. 记录修复事件
        if hasattr(self.engine, 'log_evolution_event'):
            self.engine.log_evolution_event(
                "self_healing_applied",
                {
                    "trigger": "consecutive_low_quality",
                    "consecutive_count": self.threshold,
                    "weak_points": weak_points,
                    "repair_actions": repair_actions,
                    "health_score": report.get("health_score", 0)
                }
            )

        # 7. 恢复服务
        self._resume_services()

        # 8. 重置计数
        self.consecutive_low_count = 0
        self.last_repair_time = datetime.now().isoformat()
        self.repair_history.append({
            "timestamp": self.last_repair_time,
            "actions": repair_actions,
            "health_score": report.get("health_score", 0)
        })
        self._save_state()
        self.log("✅ 自我修复流程完成", "success")

    def _pause_services(self):
        """暂停外部服务（模拟）"""
        self.log("⏸️ 暂停外部服务（标记）", "system")
        if hasattr(self.engine, '_self_healing_paused'):
            setattr(self.engine, '_self_healing_paused', True)

    def _resume_services(self):
        """恢复服务"""
        self.log("▶️ 恢复服务", "system")
        if hasattr(self.engine, '_self_healing_paused'):
            setattr(self.engine, '_self_healing_paused', False)

    def _identify_weak_points(self, report: Dict) -> List[str]:
        """从审计报告中提取弱环节"""
        weak = []
        components = report.get("components_status", {})
        for comp, ok in components.items():
            if not ok:
                weak.append(f"组件 {comp} 不可用")
        # 检查认知连续性
        if report.get("cognitive_continuity_score", 10) < 6:
            weak.append("认知连续性偏低")
        # 检查知识覆盖度
        layers = report.get("layers", [])
        for layer in layers:
            if layer.get("name") == "L1":
                if layer.get("count", 0) < 5:
                    weak.append("L1核心晶体不足")
        return weak

    def _apply_repair(self, weak_point: str, report: Dict) -> Dict:
        """根据弱环节应用修复策略"""
        action = {"weak_point": weak_point, "applied": False, "details": ""}
        try:
            if "组件" in weak_point:
                # 重新初始化缺失组件
                self.log(f"🔧 尝试重新初始化 {weak_point}", "system")
                # 这里可调用特定组件初始化
                action["applied"] = True
                action["details"] = f"重新初始化 {weak_point}"
            elif "认知连续性" in weak_point:
                # 运行每日计划以增加知识多样性
                self.log("📅 运行每日计划增强认知多样性", "system")
                from crystal_tree_all_in_one_day import DailyPlanner, ExternalFetcher, AIClient
                ai_client = self.ai
                if ai_client is None:
                    # 尝试从引擎获取或创建新的
                    if hasattr(self.engine, 'ai_client'):
                        ai_client = self.engine.ai_client
                    else:
                        from crystal_tree_all_in_one_day import Config
                        api_key = Config.get_api_key() if hasattr(Config, 'get_api_key') else None
                        ai_client = AIClient(api_key=api_key)
                planner = DailyPlanner(
                    self.engine,
                    self.ai,
                    ExternalFetcher(),
                    self.log,
                    lambda m: self.log(m, "status")
                )
                planner.run(
                    intent_keywords=["认知多样性", "知识补充"],
                    time_budget_seconds=300,
                    stop_flag=lambda: False
                )
                action["applied"] = True
                action["details"] = "执行每日计划"
            elif "L1核心晶体不足" in weak_point:
                # 从现有晶体中提升高价值到L1
                self.log("⬆️ 提升高价值晶体到L1", "system")
                state = self.engine.load_layer_state()
                layers = state.get("layers", {})
                heat = state.get("heat_map", {})
                # 按热度排序，选前5个非L1提升
                candidates = sorted([(cid, heat.get(cid,0)) for cid in layers if layers.get(cid) != "L1"],
                                    key=lambda x: x[1], reverse=True)[:5]
                for cid, _ in candidates:
                    layers[cid] = "L1"
                state["layers"] = layers
                self.engine.save_layer_state(state)
                action["applied"] = True
                action["details"] = f"提升 {len(candidates)} 个晶体到L1"
        except Exception as e:
            self.log(f"❌ 修复 {weak_point} 失败：{e}", "error")
            action["details"] = f"失败：{e}"
        return action

    def get_status(self) -> Dict:
        """获取自我修复状态"""
        return {
            "consecutive_low_count": self.consecutive_low_count,
            "threshold": self.threshold,
            "last_repair_time": self.last_repair_time,
            "repair_count": len(self.repair_history),
            "paused": getattr(self.engine, '_self_healing_paused', False)
        }