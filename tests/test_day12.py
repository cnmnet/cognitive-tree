#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 12 功能测试套件
验证：可验证主张提取器 + SVR-MAD + 沙盒执行 + M3MAD-Bench
"""

import sys
import os
import json
import unittest
from pathlib import Path

# 设置项目路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入需要测试的模块
from scripts.claim_extractor import ClaimExtractor
from scripts.svr_mad import SVRMADValidator
from scripts.m3mad_bench import M3MADBench
from crystal_tree_all_in_one_day import Config, FileIO, AIClient, CrystalEngine


class TestDay12(unittest.TestCase):
    """Day 12 功能测试"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        FileIO.ensure_directories()
        FileIO.ensure_default_files()
        cls.ai = AIClient()
        cls.engine = CrystalEngine(FileIO(), ai_client=cls.ai)
        
    def test_01_claim_extractor_basic(self):
        """测试1: 可验证主张提取器 - 基本功能"""
        print("\n🔍 测试1: 可验证主张提取器 - 基本功能")
        
        extractor = ClaimExtractor()
        test_text = """
        新方案比旧方案效率提升35%，时间成本降低20%。
        项目需要3天完成，预计耗时24小时。
        用户满意度从70%提升到85%。
        """
        
        claims = extractor.extract(test_text)
        
        self.assertGreater(len(claims), 0, "应该提取到至少一个主张")
        print(f"  ✅ 提取到 {len(claims)} 个主张")
        
        # 验证每个主张都有必要的字段
        for claim in claims:
            self.assertIn("type", claim, "主张应该包含类型")
            self.assertIn("original", claim, "主张应该包含原文")
            self.assertIn("test_code", claim, "主张应该包含测试代码")
            self.assertIn("confidence", claim, "主张应该包含置信度")
            print(f"    - {claim['type']}: {claim['original'][:30]}... (置信度: {claim['confidence']:.2f})")
        
        print("  ✅ 测试通过")
    
    def test_02_claim_extractor_test_code(self):
        """测试2: 可验证主张提取器 - 测试代码生成"""
        print("\n🔍 测试2: 可验证主张提取器 - 测试代码生成")
        
        extractor = ClaimExtractor()
        test_text = "新方案效率提升35%"
        
        claims = extractor.extract(test_text)
        self.assertGreater(len(claims), 0, "应该提取到主张")
        
        claim = claims[0]
        test_code = claim.get("test_code", "")
        
        self.assertIn("def test_", test_code, "测试代码应该包含测试函数")
        self.assertIn("assert", test_code, "测试代码应该包含断言")
        self.assertIn("print", test_code, "测试代码应该包含输出")
        
        print(f"  生成的测试代码预览:\n{test_code[:200]}...")
        print("  ✅ 测试通过")
    
    def test_03_svr_mad_basic(self):
        """测试3: SVR-MAD 贝叶斯后验验证 - 基本功能"""
        print("\n📊 测试3: SVR-MAD 贝叶斯后验验证 - 基本功能")
        
        validator = SVRMADValidator()
        role_names = ["激进者", "保守者", "结构主义者"]
        prior = {"激进者": 0.3, "保守者": 0.6, "结构主义者": 0.4}
        likelihood = {"激进者": 0.85, "保守者": 0.70, "结构主义者": 0.75}
        
        posterior = validator.compute_posterior(role_names, prior, likelihood)
        
        # 验证总和为1
        total = sum(posterior.values())
        self.assertAlmostEqual(total, 1.0, places=4, msg="后验概率总和应该为1")
        
        # 验证每个概率在0-1之间
        for name, prob in posterior.items():
            self.assertGreaterEqual(prob, 0.0, f"{name} 的概率不应小于0")
            self.assertLessEqual(prob, 1.0, f"{name} 的概率不应大于1")
        
        print("  先验:")
        for name, prob in prior.items():
            print(f"    {name}: {prob:.2%}")
        print("  后验:")
        for name, prob in posterior.items():
            print(f"    {name}: {prob:.2%}")
        
        print("  ✅ 测试通过")
    
    def test_04_svr_mad_posterior_ordering(self):
        """测试4: SVR-MAD - 后验排序验证"""
        print("\n📊 测试4: SVR-MAD - 后验排序验证")
        
        validator = SVRMADValidator()
        
        # 场景1: 先验和似然一致
        role_names = ["A", "B", "C"]
        prior = {"A": 0.7, "B": 0.2, "C": 0.1}
        likelihood = {"A": 0.9, "B": 0.4, "C": 0.2}
        
        posterior1 = validator.compute_posterior(role_names, prior, likelihood)
        top1 = max(posterior1.items(), key=lambda x: x[1])[0]
        self.assertEqual(top1, "A", "高先验+高似然应该得到最高后验")
        print(f"  场景1: 最高后验 = {top1} (正确)")
        
        # 场景2: 先验低但似然高
        prior2 = {"A": 0.2, "B": 0.7, "C": 0.1}
        likelihood2 = {"A": 0.9, "B": 0.3, "C": 0.2}
        posterior2 = validator.compute_posterior(role_names, prior2, likelihood2)
        top2 = max(posterior2.items(), key=lambda x: x[1])[0]
        self.assertEqual(top2, "A", "低先验+高似然可能逆转排序")
        print(f"  场景2: 最高后验 = {top2} (正确 - 似然逆转了先验)")
        
        print("  ✅ 测试通过")
    
    def test_05_m3mad_bench_integration(self):
        """测试5: M3MAD-Bench - 集成测试（不调用真实AI）"""
        print("\n📊 测试5: M3MAD-Bench - 集成测试")
        
        # 创建一个模拟的AI客户端
        class MockAIClient:
            def chat(self, prompt, **kwargs):
                return """这是一个模拟的回答。
                1. 首先，需要明确目标。
                2. 其次，制定详细计划。
                3. 最后，执行并反馈。
                
                预计效果提升30%左右。"""
        
        mock_ai = MockAIClient()
        bench = M3MADBench(ai_client=mock_ai, engine=self.engine)
        
        # 运行少量测试
        result = bench.run_benchmark(max_tasks_per_domain=1)
        
        self.assertIn("summary", result, "报告应该包含摘要")
        self.assertIn("domain_scores", result, "报告应该包含各领域评分")
        self.assertIn("details", result, "报告应该包含详细信息")
        
        summary = result["summary"]
        print(f"  综合评分: {summary.get('composite_score', 0):.3f}")
        print(f"  测试任务数: {summary.get('total_tasks', 0)}")
        
        print("  ✅ 测试通过")
    
    def test_06_sandbox_execution(self):
        """测试6: 沙盒执行 - 基本功能"""
        print("\n🔬 测试6: 沙盒执行 - 基本功能")
        
        # 测试通过的代码
        test_code_pass = """
def main():
    print("[PASS] 沙盒测试通过")
    return 0
"""
        
        result_pass = self.engine.execute_sandbox(test_code_pass, timeout=5)
        print(f"  通过代码执行结果: success={result_pass['success']}")
        self.assertTrue(result_pass["success"], "正确的代码应该执行成功")
        
        # 测试失败的代码
        test_code_fail = """
def main():
    raise ValueError("测试错误")
"""
        
        result_fail = self.engine.execute_sandbox(test_code_fail, timeout=5)
        print(f"  失败代码执行结果: success={result_fail['success']}")
        self.assertFalse(result_fail["success"], "有错误的代码应该执行失败")
        
        print("  ✅ 测试通过")
    
    def test_07_integration_claim_to_test(self):
        """测试7: 端到端 - 从主张提取到沙盒执行"""
        print("\n🔗 测试7: 端到端 - 从主张提取到沙盒执行")
        
        # 1. 提取主张
        extractor = ClaimExtractor()
        test_text = "系统响应时间从2秒减少到1.5秒，性能提升25%"
        claims = extractor.extract(test_text)
        
        self.assertGreater(len(claims), 0, "应该提取到主张")
        print(f"  提取到 {len(claims)} 个主张")
        
        # 2. 获取测试代码
        claim = claims[0]
        test_code = claim.get("test_code", "")
        self.assertTrue(test_code, "应该有测试代码")
        print(f"  测试代码长度: {len(test_code)} 字符")
        
        # 3. 沙盒执行
        result = self.engine.execute_sandbox(test_code, timeout=10)
        print(f"  沙盒执行结果: success={result['success']}")
        
        # 4. 生成测试套件
        output_dir = Config.DATA_ROOT / "skills" / "_test_suite"
        test_file = extractor.generate_test_suite(claims, output_dir)
        
        self.assertTrue(test_file.exists(), "测试套件文件应该生成")
        print(f"  测试套件已生成: {test_file}")
        
        print("  ✅ 测试通过")
    
    def test_08_run_all_day12_features(self):
        """测试8: 运行所有Day 12功能（综合测试）"""
        print("\n🚀 测试8: 运行所有Day 12功能（综合测试）")
        
        # 创建一个模拟的辩论结果
        mock_debate_result = {
            "rounds": [
                {
                    "round": 1,
                    "answers": [
                        {
                            "role": "激进者",
                            "answer": "新方案比旧方案效率提升35%，应该立即推广。"
                        },
                        {
                            "role": "保守者",
                            "answer": "需要3天时间验证，风险降低20%。"
                        },
                        {
                            "role": "结构主义者",
                            "answer": "用户满意度从70%提升到85%，建议分阶段实施。"
                        }
                    ],
                    "audit": {
                        "evidence_scores": {
                            "激进者": 0.7,
                            "保守者": 0.8,
                            "结构主义者": 0.75
                        },
                        "summary": "辩论完成"
                    }
                }
            ],
            "board_version": "建议采纳保守者的分阶段方案，预计效果提升30%。",
            "employee_version": "第一步：评估当前状态；第二步：制定计划；第三步：执行。",
            "novice_version": "简单来说，就是先试点再推广。",
            "expert_version": "详细分析显示，方案A优于方案B约25%。"
        }
        
        # 1. 提取主张
        extractor = ClaimExtractor()
        claims = extractor.extract_from_debate_result(mock_debate_result)
        print(f"  从辩论中提取到 {len(claims)} 个主张")
        
        # 2. 执行SVR-MAD
        validator = SVRMADValidator(engine=self.engine)
        role_key_map = validator.get_role_key_map(mock_debate_result)
        svr_result = validator.compute_posterior_for_debate(mock_debate_result, role_key_map)
        print(f"  SVR-MAD: 最高后验角色 = {svr_result.get('top_role', '未知')}")
        print(f"    置信度差距: {svr_result.get('confidence_gap', 0):.3f}")
        
        # 3. 沙盒执行
        if claims:
            test_code = claims[0].get("test_code", "")
            if test_code:
                sandbox_result = self.engine.execute_sandbox(test_code, timeout=10)
                print(f"  沙盒执行: success={sandbox_result['success']}")
        
        print("  ✅ 综合测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("🧪 Day 12 功能测试套件")
    print("=" * 70)
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDay12)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"  运行测试数: {result.testsRun}")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ 所有测试通过！可以开始下一天任务。")
    else:
        print("\n❌ 部分测试失败，请检查后再继续。")
        for failure in result.failures:
            print(f"  失败: {failure[0]}")
        for error in result.errors:
            print(f"  错误: {error[0]}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)