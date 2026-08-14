#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from governance.config import Config

@dataclass
class LayerContribution:
    """层级贡献数据"""
    layer_name: str  # "L1", "L2", "L3"
    crystal_count: int
    contribution_percent: float  # 0-100
    trend: str  # "up", "down", "stable"
    trend_value: float  # 变化百分比
    heat_avg: float
    last_updated: str


@dataclass
class AuditReport:
    """审计报告"""
    timestamp: str
    layers: List[LayerContribution]
    total_crystals: int
    health_score: float  # 0-10
    components_status: Dict[str, bool]
    cognitive_continuity_score: float  # 0-10
    fingerprint_change_rate: float  # 0-1
    recommendations: List[str]
    version: str = "1.0"


class LayerAuditService:
    """
    Harness 分解审计服务（常驻后台）

    每周自动运行一次审计，更新《系统层级贡献报告》
    """

    def __init__(self, engine: Any, file_io: Any):
        self.engine = engine
        self.files = file_io
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._audit_lock = threading.Lock()
        self._last_audit_time: Optional[datetime] = None
        self._audit_history: List[Dict] = []
        self._load_state()

    def _get_report_path(self) -> Path:
        """获取报告文件路径"""
        return Config.DATA_ROOT / "系统日志" / "层级贡献报告.json"

    def _load_state(self):
        """加载审计状态"""
        report_path = self._get_report_path()
        if report_path.exists():
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._audit_history = data.get("history", [])
                    last = data.get("last_audit")
                    if last:
                        self._last_audit_time = datetime.fromisoformat(last)
            except:
                self._audit_history = []

    def _save_state(self, report: AuditReport):
        """保存审计状态"""
        report_path = self._get_report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)

        # 转换报告为字典
        report_dict = {
            "timestamp": report.timestamp,
            "layers": [
                {
                    "layer_name": l.layer_name,
                    "crystal_count": l.crystal_count,
                    "contribution_percent": l.contribution_percent,
                    "trend": l.trend,
                    "trend_value": l.trend_value,
                    "heat_avg": l.heat_avg,
                    "last_updated": l.last_updated
                }
                for l in report.layers
            ],
            "total_crystals": report.total_crystals,
            "health_score": report.health_score,
            "components_status": report.components_status,
            "cognitive_continuity_score": report.cognitive_continuity_score,
            "fingerprint_change_rate": report.fingerprint_change_rate,
            "recommendations": report.recommendations,
            "version": report.version
        }

        # 添加到历史
        self._audit_history.append(report_dict)

        # 只保留最近52周
        if len(self._audit_history) > Config.AUDIT_CONFIG.get("history_limit", 52):
            self._audit_history = self._audit_history[-Config.AUDIT_CONFIG.get("history_limit", 52):]

        # 保存
        data = {
            "last_audit": report.timestamp,
            "history": self._audit_history,
            "latest": report_dict
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def run_audit(self) -> AuditReport:
        """
        执行一次完整的层级贡献审计

        Returns:
            AuditReport: 审计报告
        """
        # 1. 更新晶体分层
        L1, L2, L3 = self.engine.update_crystal_layers()
        state = self.engine.load_layer_state()
        heat_map = state.get("heat_map", {})

        # 2. 计算各层级贡献
        total = len(L1) + len(L2) + len(L3)
        layer_contributions = []

        layer_data = [
            ("L1", L1, 3.0),  # L1 权重最高
            ("L2", L2, 2.0),
            ("L3", L3, 1.0),
        ]

        for name, crystals, weight in layer_data:
            count = len(crystals)
            # 计算贡献度：数量 * 权重 / 总数 * 100
            if total > 0:
                base_percent = (count / total) * 100
                # 加权调整
                weighted_percent = base_percent * (weight / 2.0)
            else:
                weighted_percent = 0

            # 计算平均热度
            heats = [heat_map.get(c.id, 0.0) for c in crystals]
            heat_avg = sum(heats) / max(1, len(heats))

            # 计算趋势（与上次对比）
            trend, trend_value = self._calculate_trend(name, count)

            layer_contributions.append(LayerContribution(
                layer_name=name,
                crystal_count=count,
                contribution_percent=round(min(100, weighted_percent), 1),
                trend=trend,
                trend_value=trend_value,
                heat_avg=round(heat_avg, 2),
                last_updated=datetime.now().isoformat()
            ))

        # 3. 检查四个组件完整性
        components_status = self._check_components()

        # 4. 计算认知连续性评分
        continuity_score, fingerprint_rate = self._calculate_cognitive_continuity()

        # 5. 生成健康评分
        health_score = self._calculate_health_score(
            layer_contributions,
            components_status,
            continuity_score
        )

        # 6. 生成建议
        recommendations = self._generate_recommendations(
            layer_contributions,
            components_status,
            continuity_score
        )

        # 7. 创建报告
        report = AuditReport(
            timestamp=datetime.now().isoformat(),
            layers=layer_contributions,
            total_crystals=total,
            health_score=round(health_score, 1),
            components_status=components_status,
            cognitive_continuity_score=round(continuity_score, 1),
            fingerprint_change_rate=round(fingerprint_rate, 3),
            recommendations=recommendations
        )

        # 8. 保存
        self._save_state(report)
        self._last_audit_time = datetime.now()

        # 9. 记录到进化日志
        self.engine.log_evolution_event(
            "harness_audit_completed",
            {
                "health_score": health_score,
                "total_crystals": total,
                "components_ok": all(components_status.values()),
                "continuity_score": continuity_score,
                "trigger": "scheduled_audit"
            }
        )

        return report

    def _calculate_trend(self, layer_name: str, current_count: int) -> tuple:
        """计算层级趋势"""
        if not self._audit_history:
            return "stable", 0.0

        # 获取上次审计数据
        last = self._audit_history[-1]
        last_layers = last.get("layers", [])
        last_count = 0
        for l in last_layers:
            if l.get("layer_name") == layer_name:
                last_count = l.get("crystal_count", 0)
                break

        if last_count == 0:
            return "stable" if current_count == 0 else "up", 100.0

        change = ((current_count - last_count) / last_count) * 100
        if change > 5:
            return "up", round(change, 1)
        elif change < -5:
            return "down", round(abs(change), 1)
        else:
            return "stable", round(change, 1)

    def _check_components(self) -> Dict[str, bool]:
        """检查四个组件是否完整"""
        components = Config.AUDIT_CONFIG.get("component_checks", [])
        result = {}
        for comp in components:
            # 检查类是否存在
            exists = comp in globals()
            # 检查实例是否存在
            if comp == "CrystalEngine":
                exists = exists and hasattr(self.engine, "parse_crystals")
            elif comp == "MetaLayer":
                exists = exists and hasattr(self.engine, "meta")
            elif comp == "CheapGate":
                exists = exists and hasattr(self.engine, "cheap_gate")
            result[comp] = exists
        return result

    def _calculate_cognitive_continuity(self) -> tuple:
        """计算认知连续性评分（Day 3 冷启动修正：阈值 20）"""
        try:
            fingerprint_data = self.files.read_fingerprint()
            fp = fingerprint_data.get("fingerprint", {})
            evolution_log = fp.get("evolution_log", [])

            window = Config.AUDIT_CONFIG.get("cognitive_continuity_window", 10)
            recent_logs = evolution_log[-window:] if evolution_log else []

            # ===== Day 3 修改：阈值从 3 提升到 20 =====
            if len(recent_logs) < 20:
                # 记录 WARNING 日志
                msg = f"数据不足（仅 {len(recent_logs)} 条记录，需要 20 条），认知连续性评分锁定为 3.0/10"
                if hasattr(self, 'engine') and hasattr(self.engine, '_append_change_log'):
                    self.engine._append_change_log("冷启动评分修正", msg)
                else:
                    print(f"[WARNING] {msg}")
                return 3.0, 0.0

            # ===== 数据充足（≥20条），使用实际计算值 =====
            changes = []
            for log in recent_logs:
                if "changes" in log:
                    changes.extend(log["changes"])

            total_dimensions = 5
            change_rate = len(changes) / (total_dimensions * max(1, len(recent_logs)))

            # 评分：变化率越低，连续性越好
            if change_rate < 0.1:
                score = 9.0
            elif change_rate < 0.15:
                score = 8.0
            elif change_rate < 0.2:
                score = 7.0
            elif change_rate < 0.25:
                score = 6.0
            else:
                score = 5.0

            return score, change_rate

        except Exception as e:
            print(f"⚠️ 认知连续性计算失败: {e}")
            return 3.0, 0.0

    def _calculate_health_score(self, layers: List[LayerContribution],
                                components: Dict[str, bool],
                                continuity: float) -> float:
        """计算健康评分（0-10）"""
        score = 0.0

        # 1. 层级贡献平衡度（最多3分）
        if layers:
            contributions = [l.contribution_percent for l in layers]
            if contributions:
                # 理想分布：L1 > L2 > L3
                if len(contributions) >= 3:
                    if contributions[0] > contributions[1] > contributions[2]:
                        score += 2.5
                    elif contributions[0] > contributions[1]:
                        score += 2.0
                    else:
                        score += 1.5
                else:
                    score += 2.0

        # 2. 组件完整性（最多3分）
        if all(components.values()):
            score += 3.0
        elif len([v for v in components.values() if v]) >= 3:
            score += 2.0
        elif len([v for v in components.values() if v]) >= 2:
            score += 1.0

        # 3. 认知连续性（最多3分）
        if continuity >= 8.0:
            score += 3.0
        elif continuity >= 6.0:
            score += 2.0
        elif continuity >= 4.0:
            score += 1.0

        # 4. 晶体数量（最多1分）
        total = sum(l.crystal_count for l in layers)
        if total >= 100:
            score += 1.0
        elif total >= 50:
            score += 0.5

        return min(10.0, score)

    def _generate_recommendations(self, layers: List[LayerContribution],
                                   components: Dict[str, bool],
                                   continuity: float) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 检查组件完整性
        for comp, ok in components.items():
            if not ok:
                recommendations.append(f"⚠️ 组件 {comp} 不可用，请检查系统完整性")

        # 检查认知连续性
        if continuity < 6.0:
            recommendations.append("📉 认知连续性偏低，建议减少剧烈偏好调整，保持一致性")

        # 检查层级分布
        if layers:
            l1 = next((l for l in layers if l.layer_name == "L1"), None)
            l3 = next((l for l in layers if l.layer_name == "L3"), None)
            if l1 and l3:
                if l1.crystal_count < l3.crystal_count:
                    recommendations.append("📊 L1晶体少于L3，建议提升核心晶体质量，或手动固定高价值晶体到L1")

        # 检查晶体总量
        total = sum(l.crystal_count for l in layers)
        if total < 20:
            recommendations.append("📚 晶体总数偏少（<20），建议增加晶体化操作")

        if not recommendations:
            recommendations.append("✅ 系统健康状态良好，继续保持！")

        return recommendations

    def start_background(self):
        """启动后台审计服务"""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()
        print("📊 层级审计服务已启动（每周自动运行）")

    def stop_background(self):
        """停止后台审计服务"""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        print("📊 层级审计服务已停止")

    def _background_loop(self):
        """后台循环"""
        while not self._stop_event.is_set():
            try:
                # 检查是否应该运行审计
                if self._should_run_audit():
                    if self._audit_lock.acquire(blocking=False):
                        try:
                            print("📊 开始执行每周自动审计...")
                            report = self.run_audit()
                            print(f"📊 审计完成 - 健康评分: {report.health_score}/10")
                        finally:
                            self._audit_lock.release()
                    else:
                        print("⚠️ 审计任务正在运行，跳过本轮")

                # 每小时检查一次
                for _ in range(3600):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"⚠️ 后台审计异常: {e}")
                time.sleep(60)

    def _should_run_audit(self) -> bool:
        """判断是否应该运行审计"""
        if not Config.AUDIT_CONFIG.get("enabled", True):
            return False

        if self._last_audit_time is None:
            return True

        interval_hours = Config.AUDIT_CONFIG.get("interval_hours", 168)
        elapsed = (datetime.now() - self._last_audit_time).total_seconds() / 3600
        return elapsed >= interval_hours

    def get_latest_report(self) -> Optional[Dict]:
        """获取最新审计报告"""
        report_path = self._get_report_path()
        if not report_path.exists():
            return None
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("latest")
        except:
            return None

    def get_audit_history(self, limit: int = 10) -> List[Dict]:
        """获取审计历史"""
        return self._audit_history[-limit:]
