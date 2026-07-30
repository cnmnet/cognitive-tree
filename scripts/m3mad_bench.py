#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3MAD-Bench 标准化评估模块 (Day 12)
评估三个维度：多域任务（推理/知识/创意）、多模态输入（文本/文件/对话历史）、多维指标（准确性/效率/多样性）

论文依据: M3MAD-Bench (arXiv:2601.01234)
"""

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import sys

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from crystal_tree_all_in_one_day import Config, FileIO, AIClient, CrystalEngine
except ImportError:
    # 如果直接运行，使用相对导入
    from ..crystal_tree_all_in_one_day import Config, FileIO, AIClient, CrystalEngine


class M3MADBench:
    """
    M3MAD-Bench 标准化评估框架
    
    评估三个维度：
    - 多域任务：推理/知识/创意
    - 多模态输入：文本/文件/对话历史
    - 多维指标：准确性/效率/多样性
    """
    
    # 标准测试集（多域任务）
    BENCHMARK_TASKS = {
        "reasoning": [
            "如果A比B高30%，B比C高20%，那么A比C高百分之几？",
            "一个项目有3个阶段，每个阶段有2个检查点，每个检查点需要3天，总共需要多少天？",
            "如果团队规模从10人增加到15人，效率提升20%，那么人均产出变化是多少？"
        ],
        "knowledge": [
            "什么是认知晶体树的核心操作原则？",
            "解释八道防线在AI系统中的工作原理。",
            "Gödel Agent的递归自我改进机制是如何工作的？"
        ],
        "creative": [
            "设计一个结合AI和冥想的新产品概念。",
            "提出3种将中国古典哲学融入现代AI系统的方法。",
            "如果认知晶体树是一本小说，它的主角和反派分别是什么？"
        ]
    }
    
    def __init__(self, ai_client: Optional[AIClient] = None, engine: Optional[CrystalEngine] = None):
        self.ai = ai_client or AIClient()
        self.engine = engine or CrystalEngine(FileIO(), ai_client=self.ai)
        self.results: List[Dict] = []
        
    def run_benchmark(self, max_tasks_per_domain: int = 2) -> Dict[str, Any]:
        """
        运行完整基准测试
        
        Args:
            max_tasks_per_domain: 每个领域最多测试的任务数
            
        Returns:
            完整的评估报告
        """
        print("=" * 70)
        print("📊 M3MAD-Bench 标准化评估")
        print("=" * 70)
        
        all_results = []
        
        for domain, tasks in self.BENCHMARK_TASKS.items():
            print(f"\n🔬 评估领域: {domain}")
            print("-" * 50)
            
            for i, task in enumerate(tasks[:max_tasks_per_domain]):
                print(f"\n  任务 {i+1}: {task[:60]}...")
                result = self._evaluate_single_task(domain, task)
                all_results.append(result)
                self._print_task_result(result)
        
        # 汇总报告
        report = self._aggregate_results(all_results)
        self._save_report(report)
        
        return report
    
    def _evaluate_single_task(self, domain: str, task: str) -> Dict[str, Any]:
        """
        评估单个任务
        
        Returns:
            {
                "domain": str,
                "task": str,
                "accuracy": float,      # 0-1
                "efficiency": float,    # 0-1 (基于响应时间)
                "diversity": float,     # 0-1 (基于答案多样性)
                "response": str,
                "timestamp": str
            }
        """
        start_time = time.time()
        
        # 调用AI获取回答
        try:
            response = self.ai.chat(
                f"请回答以下问题，给出详细、结构化的答案：\n\n{task}",
                temperature=0.7
            )
        except Exception as e:
            response = f"（AI调用失败: {e}）"
        
        elapsed = time.time() - start_time
        
        # 计算指标
        accuracy = self._compute_accuracy(task, response)
        efficiency = self._compute_efficiency(elapsed)
        diversity = self._compute_diversity(response)
        
        return {
            "domain": domain,
            "task": task,
            "accuracy": round(accuracy, 3),
            "efficiency": round(efficiency, 3),
            "diversity": round(diversity, 3),
            "response": response,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.now().isoformat()
        }
    
    def _compute_accuracy(self, task: str, response: str) -> float:
        """
        计算准确性（0-1）
        基于：是否包含数字、是否结构化、是否与任务相关
        """
        if not response or len(response) < 20:
            return 0.0
        
        score = 0.0
        
        # 1. 是否包含数字或具体数据 (0-0.4)
        if re.search(r'\d+', response):
            score += 0.2
        if re.search(r'\d+%', response) or re.search(r'\d+[\.\d]*%', response):
            score += 0.2
        
        # 2. 是否结构化 (0-0.3)
        if re.search(r'[1-9][\.、]', response):
            score += 0.15
        if '首先' in response or '第一' in response or '步骤' in response:
            score += 0.15
        
        # 3. 是否与任务相关 (0-0.3)
        task_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', task))
        response_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', response))
        if task_keywords and response_keywords:
            overlap = len(task_keywords & response_keywords) / len(task_keywords)
            score += min(0.3, overlap * 0.3)
        
        return min(1.0, score)
    
    def _compute_efficiency(self, elapsed_seconds: float) -> float:
        """
        计算效率（0-1）
        基于响应时间：<5秒=1.0，5-15秒=0.7，15-30秒=0.4，>30秒=0.1
        """
        if elapsed_seconds < 5:
            return 1.0
        elif elapsed_seconds < 15:
            return 0.7
        elif elapsed_seconds < 30:
            return 0.4
        elif elapsed_seconds < 60:
            return 0.2
        else:
            return 0.1
    
    def _compute_diversity(self, response: str) -> float:
        """
        计算多样性（0-1）
        基于：词汇丰富度、结构多样性、观点多样性
        """
        if not response or len(response) < 50:
            return 0.0
        
        score = 0.0
        
        # 1. 词汇丰富度 (0-0.4)
        words = re.findall(r'[\u4e00-\u9fff]{2,}', response)
        unique_words = set(words)
        if len(words) >= 20:
            word_ratio = len(unique_words) / len(words)
            score += min(0.4, word_ratio * 0.8)
        
        # 2. 结构多样性 (0-0.3)
        if '、' in response or '；' in response:
            score += 0.1
        if re.search(r'[1-9][\.、]', response):
            score += 0.1
        if '例如' in response or '比如' in response:
            score += 0.1
        
        # 3. 观点多样性 (0-0.3)
        perspective_keywords = ['一方面', '另一方面', '同时', '此外', '另外']
        for kw in perspective_keywords:
            if kw in response:
                score += 0.06
        score = min(0.3, score)
        
        return min(1.0, score)
    
    def _aggregate_results(self, results: List[Dict]) -> Dict[str, Any]:
        """
        聚合所有测试结果
        """
        if not results:
            return {"error": "无测试结果"}
        
        # 按领域分组
        by_domain = {}
        for r in results:
            domain = r["domain"]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(r)
        
        # 计算各领域平均分
        domain_scores = {}
        for domain, items in by_domain.items():
            domain_scores[domain] = {
                "accuracy": round(sum(i["accuracy"] for i in items) / len(items), 3),
                "efficiency": round(sum(i["efficiency"] for i in items) / len(items), 3),
                "diversity": round(sum(i["diversity"] for i in items) / len(items), 3),
                "count": len(items)
            }
        
        # 计算总平均分
        all_acc = [r["accuracy"] for r in results]
        all_eff = [r["efficiency"] for r in results]
        all_div = [r["diversity"] for r in results]
        
        summary = {
            "total_tasks": len(results),
            "overall_accuracy": round(sum(all_acc) / len(all_acc), 3),
            "overall_efficiency": round(sum(all_eff) / len(all_eff), 3),
            "overall_diversity": round(sum(all_div) / len(all_div), 3),
            "composite_score": round((sum(all_acc) + sum(all_eff) + sum(all_div)) / (len(all_acc) * 3), 3)
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "domain_scores": domain_scores,
            "summary": summary,
            "details": results
        }
    
    def _print_task_result(self, result: Dict):
        """打印单个任务结果"""
        print(f"    ✅ 准确性: {result['accuracy']:.2f} | "
              f"效率: {result['efficiency']:.2f} | "
              f"多样性: {result['diversity']:.2f} | "
              f"耗时: {result['elapsed_seconds']:.1f}s")
    
    def _save_report(self, report: Dict):
        """保存报告到文件"""
        output_path = Config.DATA_ROOT / "系统日志" / "m3mad_bench_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 报告已保存至: {output_path}")
        
        # 同时生成可读版本
        readable_path = Config.DATA_ROOT / "系统日志" / "m3mad_bench_report.md"
        with open(readable_path, "w", encoding="utf-8") as f:
            f.write(self._format_report_readable(report))
        
        print(f"📄 可读报告已保存至: {readable_path}")
    
    def _format_report_readable(self, report: Dict) -> str:
        """生成可读的报告格式"""
        lines = []
        lines.append("# M3MAD-Bench 评估报告")
        lines.append("")
        lines.append(f"**评估时间**: {report.get('timestamp', '未知')}")
        lines.append(f"**总任务数**: {report.get('summary', {}).get('total_tasks', 0)}")
        lines.append("")
        
        # 总体评分
        summary = report.get("summary", {})
        lines.append("## 总体评分")
        lines.append("")
        lines.append(f"- 准确性: **{summary.get('overall_accuracy', 0):.2f}**")
        lines.append(f"- 效率: **{summary.get('overall_efficiency', 0):.2f}**")
        lines.append(f"- 多样性: **{summary.get('overall_diversity', 0):.2f}**")
        lines.append(f"- 综合评分: **{summary.get('composite_score', 0):.2f}**")
        lines.append("")
        
        # 各领域评分
        lines.append("## 各领域评分")
        lines.append("")
        lines.append("| 领域 | 准确性 | 效率 | 多样性 | 任务数 |")
        lines.append("|------|--------|------|--------|--------|")
        for domain, scores in report.get("domain_scores", {}).items():
            lines.append(
                f"| {domain} | {scores.get('accuracy', 0):.2f} | "
                f"{scores.get('efficiency', 0):.2f} | "
                f"{scores.get('diversity', 0):.2f} | "
                f"{scores.get('count', 0)} |"
            )
        lines.append("")
        
        # 详细结果
        lines.append("## 详细结果")
        lines.append("")
        for i, item in enumerate(report.get("details", []), 1):
            lines.append(f"### 任务 {i}: {item.get('domain', '未知')}")
            lines.append("")
            lines.append(f"**问题**: {item.get('task', '')[:100]}...")
            lines.append(f"**准确性**: {item.get('accuracy', 0):.2f}")
            lines.append(f"**效率**: {item.get('efficiency', 0):.2f}")
            lines.append(f"**多样性**: {item.get('diversity', 0):.2f}")
            lines.append(f"**耗时**: {item.get('elapsed_seconds', 0):.1f}s")
            lines.append("")
            lines.append("**回答摘要**:")
            response = item.get('response', '')
            lines.append(f"```\n{response[:500]}{'...' if len(response) > 500 else ''}\n```")
            lines.append("")
        
        return "\n".join(lines)


def main():
    """命令行入口"""
    print("🚀 启动 M3MAD-Bench 评估...")
    
    # 确保文件系统初始化
    FileIO.ensure_directories()
    FileIO.ensure_default_files()
    
    # 创建AI客户端和引擎
    ai = AIClient()
    engine = CrystalEngine(FileIO(), ai_client=ai)
    
    # 运行基准测试
    bench = M3MADBench(ai_client=ai, engine=engine)
    report = bench.run_benchmark(max_tasks_per_domain=2)
    
    # 打印简要总结
    print("\n" + "=" * 70)
    print("📊 M3MAD-Bench 评估完成")
    print("=" * 70)
    summary = report.get("summary", {})
    print(f"  综合评分: {summary.get('composite_score', 0):.3f}")
    print(f"  准确性: {summary.get('overall_accuracy', 0):.3f}")
    print(f"  效率: {summary.get('overall_efficiency', 0):.3f}")
    print(f"  多样性: {summary.get('overall_diversity', 0):.3f}")
    print("=" * 70)


if __name__ == "__main__":
    main()