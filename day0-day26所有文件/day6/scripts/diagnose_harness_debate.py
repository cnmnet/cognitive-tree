#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 0：Harness分解审计基线 + 灵感池初始化
合并版双基线采集，输出诊断报告
"""

import sys
import os
import json
import time
import copy
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple

# 确保能找到主模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crystal_tree_all_in_one import (
    Config, FileIO, CrystalEngine, DebateEngine, AIClient,
    BENCHMARK_QUESTIONS, BaselineRunner
)

# =============================================================================
# 扩展的基线采集器（含消融和辩论扩展指标）
# =============================================================================
class HarnessBaselineRunner:
    """Harness 消融基线 + 辩论扩展基线采集"""

    def __init__(self):
        self.files = FileIO()
        self.engine = CrystalEngine(self.files)
        self.ai = AIClient(api_key=Config.get_api_key())
        self.roles = self._load_roles()
        self.results = []          # 存储每个问题的完整结果
        self.ablation_results = [] # 消融结果

    def _load_roles(self) -> List[Dict]:
        """从配置文件加载角色（与GUI一致）"""
        try:
            raw = json.loads(self.files.read("roles") or "{}")
        except:
            raw = {}
        roles = []
        for key, item in raw.items():
            if isinstance(item, dict):
                roles.append({"key": key, "name": item.get("name", key),
                              "instruction": item.get("instruction", "")})
        # 补全缺失角色
        fallback = [
            {"key": "radical", "name": "激进者", "instruction": "攻击默认前提，假设现有框架是错的，给出颠覆性方案。"},
            {"key": "conservative", "name": "保守者", "instruction": "风险优先，假设资源有限，给出最可落地的稳健方案。"},
            {"key": "structural", "name": "结构主义者", "instruction": "从已有晶体中寻找同构案例，用类比生成方案。"},
            {"key": "executor", "name": "执行者", "instruction": "把方案拆成步骤、资源、时间和可检查的行动清单。"},
            {"key": "auditor", "name": "审计者", "instruction": "检查证据、漏洞、冲突、过度推断和需要暂存的问题。"},
        ]
        existing_keys = {r["key"] for r in roles}
        for r in fallback:
            if r["key"] not in existing_keys and len(roles) < 5:
                roles.append(r)
                existing_keys.add(r["key"])
        return roles[:5]

    def _run_debate(self, question: str, config_overrides: Dict = None) -> Dict:
        """
        运行单次辩论，支持配置覆盖（用于消融）
        返回包含完整原始数据的字典
        """
        # 保存原始配置
        original_config = {}
        if config_overrides:
            for key, val in config_overrides.items():
                if hasattr(Config, key):
                    original_config[key] = getattr(Config, key)
                    setattr(Config, key, val)

        try:
            # 创建DebateEngine（传入角色列表，可动态修改）
            roles = copy.deepcopy(self.roles)
            # 如果配置要求移除审计员，则从角色列表中删除
            if config_overrides and config_overrides.get("REMOVE_AUDITOR", False):
                roles = [r for r in roles if r["key"] != "auditor"]

            debate = DebateEngine(
                self.ai, self.engine, roles,
                log=lambda m, l: None,   # 静默
                progress_callback=None
            )

            # 强制使用 debate_full 模式，2轮（与BaselineRunner一致）
            result = debate.run(question, mode="debate_full", max_rounds=2)
            return result
        finally:
            # 恢复配置
            for key, val in original_config.items():
                setattr(Config, key, val)

    def _extract_metrics(self, question: str, result: Dict, is_ablation: bool = False) -> Dict:
        """从辩论结果中提取全部指标（包含六维辩论基线）"""
        metrics = {
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "is_ablation": is_ablation,
        }

        rounds_data = result.get("rounds", [])
        if not rounds_data:
            return metrics

        # ---- Jaccard 相似度（各轮平均值） ----
        jaccard_per_round = []
        for rd in rounds_data:
            answers = [item["answer"] for item in rd.get("answers", [])]
            if len(answers) >= 2:
                # 使用DebateEngine的_jaccard方法（需要临时创建实例）
                temp_debate = DebateEngine(self.ai, self.engine, self.roles, lambda m, l: None)
                j = temp_debate._average_jaccard(answers)
                jaccard_per_round.append(j)
        metrics["jaccard_similarity"] = sum(jaccard_per_round) / len(jaccard_per_round) if jaccard_per_round else 0.0
        metrics["jaccard_per_round"] = jaccard_per_round

        # ---- 晶体引用率 ----
        all_text = " ".join([item["answer"] for rd in rounds_data for item in rd.get("answers", [])])
        crystal_matches = len(re.findall(r'\[C\d+\]', all_text))
        hole_matches = len(re.findall(r'\[H\d+\]', all_text))
        total_answers = sum(len(rd.get("answers", [])) for rd in rounds_data)
        metrics["crystal_reference_rate"] = (crystal_matches + hole_matches) / max(1, total_answers)

        # ---- 审计反馈平均字数 ----
        audit_feedbacks = []
        for rd in rounds_data:
            audit = rd.get("audit", {})
            for fb in audit.get("feedback_by_role", {}).values():
                if fb:
                    audit_feedbacks.append(len(str(fb)))
        metrics["audit_feedback_avg_len"] = sum(audit_feedbacks) / max(1, len(audit_feedbacks))

        # ---- 可执行建议数（通过关键词粗略统计） ----
        final = result.get("final", {})
        student = final.get("student_friendly_answer", "")
        teacher = final.get("teacher_detail", "")
        combined = student + teacher
        action_keywords = ["步骤", "建议", "方法", "操作", "执行", "具体", "可行", "方案", "检查", "落地"]
        action_count = sum(combined.count(kw) for kw in action_keywords)
        metrics["executable_actions"] = action_count // 2  # 粗略计数

        # ---- 偏见强化指数（用证据评分方差的变化表示） ----
        # 取第一轮和最后一轮的 evidence_scores 方差
        ev_scores_first = rounds_data[0].get("audit", {}).get("evidence_scores", {})
        ev_scores_last = rounds_data[-1].get("audit", {}).get("evidence_scores", {})
        if ev_scores_first and ev_scores_last:
            vals_first = list(ev_scores_first.values())
            vals_last = list(ev_scores_last.values())
            var_first = sum((x - sum(vals_first)/len(vals_first))**2 for x in vals_first) / len(vals_first) if vals_first else 0
            var_last = sum((x - sum(vals_last)/len(vals_last))**2 for x in vals_last) / len(vals_last) if vals_last else 0
            metrics["bias_amplification"] = var_last - var_first  # 正数表示偏见加强
        else:
            metrics["bias_amplification"] = 0.0

        # ---- 位置偏差指数（第一轮与最后一轮Jaccard差异） ----
        if len(jaccard_per_round) >= 2:
            metrics["position_bias"] = abs(jaccard_per_round[0] - jaccard_per_round[-1])
        else:
            metrics["position_bias"] = 0.0

        # ---- Token消耗（从AI客户端获取，需在AIClient中统计，这里简单估算） ----
        # 粗略用字符数估算
        total_chars = sum(len(item["answer"]) for rd in rounds_data for item in rd.get("answers", []))
        metrics["token_consumption"] = total_chars // 2  # 中文约2字符/token

        # ---- 用户评分（用审计分数代理） ----
        last_audit = rounds_data[-1].get("audit", {})
        ev_scores = list(last_audit.get("evidence_scores", {}).values())
        avg_audit = sum(ev_scores) / len(ev_scores) if ev_scores else 0.5
        metrics["user_rating"] = avg_audit * 5  # 映射到1-5分

        return metrics

    def collect_baselines(self) -> Dict[str, Any]:
        """
        采集所有基线：
        1. 完整系统（标准）
        2. 消融：移除向量检索
        3. 消融：移除审计员
        4. 消融：移除便宜门规则（简单禁用CheapGate检查）
        """
        print("📊 开始双基线采集...")
        all_results = {
            "full": [],
            "no_vector": [],
            "no_auditor": [],
            "no_cheapgate": []
        }

        for idx, question in enumerate(BENCHMARK_QUESTIONS):
            print(f"\n[{idx+1}/{len(BENCHMARK_QUESTIONS)}] 问题: {question[:50]}...")

            # ---- 完整系统 ----
            print("  → 完整系统")
            result_full = self._run_debate(question, config_overrides={})
            metrics_full = self._extract_metrics(question, result_full, is_ablation=False)
            all_results["full"].append(metrics_full)

            # ---- 移除向量检索 ----
            print("  → 移除向量检索")
            result_no_vec = self._run_debate(question, config_overrides={"VECTOR_SEARCH_ENABLED": False})
            metrics_no_vec = self._extract_metrics(question, result_no_vec, is_ablation=True)
            all_results["no_vector"].append(metrics_no_vec)

            # ---- 移除审计员 ----
            print("  → 移除审计员")
            result_no_aud = self._run_debate(question, config_overrides={"REMOVE_AUDITOR": True})
            metrics_no_aud = self._extract_metrics(question, result_no_aud, is_ablation=True)
            all_results["no_auditor"].append(metrics_no_aud)

            # ---- 移除便宜门（将检查函数直接返回 call_llm） ----
            print("  → 移除便宜门")
            # 我们通过修改CheapGate.check的返回值模拟，简单起见，直接设置一个标志跳过
            # 这里我们通过MonkeyPatch或覆盖方法，但为了简洁，我们使用配置标志
            # 由于CheapGate在DebateEngine内部使用，我们可以在运行前替换它的check方法
            original_check = self.engine.cheap_gate.check
            def bypass_check(*args, **kwargs):
                return {"pass": True, "action": "call_llm", "skip_llm": False, "reason": "移除便宜门"}
            self.engine.cheap_gate.check = bypass_check
            result_no_gate = self._run_debate(question, config_overrides={})
            self.engine.cheap_gate.check = original_check  # 恢复
            metrics_no_gate = self._extract_metrics(question, result_no_gate, is_ablation=True)
            all_results["no_cheapgate"].append(metrics_no_gate)

        # 汇总统计
        summary = self._aggregate(all_results)
        report = self._generate_report(all_results, summary)

        # 保存报告到文件
        report_path = Config.DATA_ROOT / "系统日志" / "双基线诊断报告.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 同时输出Markdown可读版
        md_path = Config.DATA_ROOT / "系统日志" / "双基线诊断报告.md"
        md_content = self._to_markdown(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n✅ 双基线诊断报告已保存至: {report_path}")
        return report

    def _aggregate(self, all_results: Dict) -> Dict:
        """计算各配置的平均指标"""
        summary = {}
        for config_name, metrics_list in all_results.items():
            if not metrics_list:
                continue
            # 提取数值指标（忽略字符串）
            keys = [k for k in metrics_list[0].keys() if isinstance(metrics_list[0][k], (int, float))]
            avg = {}
            for k in keys:
                vals = [m[k] for m in metrics_list if k in m]
                avg[k] = sum(vals) / len(vals) if vals else 0.0
            summary[config_name] = avg
        return summary

    def _generate_report(self, all_results: Dict, summary: Dict) -> Dict:
        """生成结构化报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(BENCHMARK_QUESTIONS),
            "configs": list(all_results.keys()),
            "summary": summary,
            "details": all_results,
            "analysis": self._analyze(summary)
        }
        return report

    def _analyze(self, summary: Dict) -> Dict:
        """分析重载层和核心弱点"""
        # 比较完整系统与消融版本的差异
        full = summary.get("full", {})
        no_vec = summary.get("no_vector", {})
        no_aud = summary.get("no_auditor", {})
        no_gate = summary.get("no_cheapgate", {})

        analysis = {
            "overloaded_layers": [],
            "core_weaknesses": []
        }

        # 定义差异阈值
        def diff(a, b, key):
            return abs(a.get(key, 0) - b.get(key, 0))

        # 检查向量检索的影响
        if diff(full, no_vec, "jaccard_similarity") > 0.05 or diff(full, no_vec, "crystal_reference_rate") > 0.1:
            analysis["overloaded_layers"].append("向量检索")
        # 检查审计员影响
        if diff(full, no_aud, "audit_feedback_avg_len") > 20 or diff(full, no_aud, "bias_amplification") > 0.05:
            analysis["overloaded_layers"].append("审计员角色")
        # 检查便宜门影响
        if diff(full, no_gate, "token_consumption") > 100 or diff(full, no_gate, "jaccard_similarity") > 0.03:
            analysis["overloaded_layers"].append("便宜门")

        # 标记核心弱点（取表现最差的三项）
        weak_candidates = []
        for config, data in summary.items():
            if config == "full":
                continue
            weak_candidates.append((config, data.get("user_rating", 0), data.get("crystal_reference_rate", 0)))
        weak_candidates.sort(key=lambda x: x[1])  # 按评分排序
        analysis["core_weaknesses"] = [f"{w[0]} (评分{w[1]:.2f}, 引用率{w[2]:.2f})" for w in weak_candidates[:3]]

        return analysis

    def _to_markdown(self, report: Dict) -> str:
        """转换为Markdown格式报告"""
        lines = ["# 双基线诊断报告", f"生成时间: {report['timestamp']}", f"测试问题数: {report['total_questions']}"]
        lines.append("\n## 各配置平均指标")
        lines.append("| 配置 | Jaccard | 晶体引用率 | 审计反馈长度 | 可执行建议 | 偏见指数 | 位置偏差 | 用户评分(1-5) | Token消耗 |")
        lines.append("|------|---------|------------|-------------|------------|----------|----------|---------------|-----------|")
        for config, data in report["summary"].items():
            lines.append(
                f"| {config} | {data.get('jaccard_similarity', 0):.3f} | {data.get('crystal_reference_rate', 0):.3f} | "
                f"{data.get('audit_feedback_avg_len', 0):.1f} | {data.get('executable_actions', 0):.1f} | "
                f"{data.get('bias_amplification', 0):.3f} | {data.get('position_bias', 0):.3f} | "
                f"{data.get('user_rating', 0):.2f} | {data.get('token_consumption', 0):.0f} |"
            )
        lines.append("\n## 分析结论")
        lines.append("### 重载层 (贡献最大的组件)")
        for layer in report["analysis"]["overloaded_layers"]:
            lines.append(f"- {layer}")
        lines.append("\n### 核心弱点 (3个)")
        for weakness in report["analysis"]["core_weaknesses"]:
            lines.append(f"- {weakness}")
        return "\n".join(lines)


# =============================================================================
# Day 0 主入口
# =============================================================================
def run_day0():
    """执行 Day 0 全部任务"""
    print("=" * 60)
    print("认知晶体树 v2.2 Day 0 任务启动")
    print("=" * 60)

    # 1. 双基线采集
    runner = HarnessBaselineRunner()
    report = runner.collect_baselines()

    # 2. 初始化灵感池（由主文件启动时完成，这里额外确保）
    inspiration_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
    if not inspiration_path.exists():
        with open(inspiration_path, "w", encoding="utf-8") as f:
            json.dump([
                {
                    "id": "INSP-001",
                    "source": "对话",
                    "content": "初始灵感：将‘八道防线’与‘沉思式反思’融合，形成免疫+智慧的协同效应",
                    "status": "待筛选",
                    "created_at": datetime.now().isoformat()
                }
            ], f, ensure_ascii=False, indent=2)
        print("✅ 灵感池.json 已初始化 (包含 INSP-001)")

    # 3. 输出报告摘要
    print("\n📌 双基线诊断报告摘要:")
    print(f"   - 重载层: {report['analysis']['overloaded_layers']}")
    print(f"   - 核心弱点: {report['analysis']['core_weaknesses']}")
    print("\n✅ Day 0 任务完成！")


if __name__ == "__main__":
    run_day0()