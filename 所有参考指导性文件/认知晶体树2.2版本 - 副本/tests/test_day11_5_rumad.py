#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 11.5 测试：RUMAD 拓扑控制原型
"""

import sys
import io
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest

from crystal_tree_all_in_one_day import RUMADController


class TestRUMAD(unittest.TestCase):
    """RUMAD 控制器测试"""

    def test_01_init(self):
        """测试初始化"""
        rumad = RUMADController(
            role_names=["激进者", "保守者", "结构主义者"],
            learning_rate=0.1,
            discount_factor=0.9,
            epsilon=0.3
        )
        self.assertEqual(rumad.n_roles, 3)
        self.assertEqual(rumad.lr, 0.1)
        self.assertEqual(rumad.gamma, 0.9)
        self.assertEqual(rumad.epsilon, 0.3)
        self.assertTrue(rumad.enabled)
        print("[OK] 测试1: 初始化通过")

    def test_02_get_state_key(self):
        """测试状态键生成"""
        rumad = RUMADController(["A", "B", "C"])
        state = rumad._get_state_key([0.8, 0.5, 0.2], 2, 0.75)
        self.assertIsInstance(state, str)
        self.assertIn("H", state)  # 包含高
        self.assertIn("M", state)  # 包含中
        self.assertIn("L", state)  # 包含低
        print(f"[OK] 测试2: 状态键生成通过 ({state})")

    def test_03_get_role_vectors(self):
        """测试角色向量提取"""
        rumad = RUMADController(["激进者", "保守者"])
        answers = [
            {"role": "激进者", "answer": "这是一个颠覆性的创新方案，需要大胆突破"},
            {"role": "保守者", "answer": "风险太高了，我们需要更加稳健的方案"}
        ]
        vectors = rumad._get_role_vectors(answers)
        self.assertEqual(len(vectors), 2)
        self.assertGreater(vectors[0], vectors[1])  # 激进者得分应该更高
        print(f"[OK] 测试3: 角色向量提取通过 ({vectors})")

    def test_04_select_action(self):
        """测试动作选择"""
        rumad = RUMADController(["A", "B", "C"])
        actions = [("A", "B"), ("A", "C"), ("B", "A"), ("B", "C"), ("C", "A"), ("C", "B")]
        state = "HML_H_E"
        
        # 第一轮应该随机选择
        action = rumad.select_action(state, actions, 1)
        self.assertIsNotNone(action)
        self.assertIn(action, actions)
        print(f"[OK] 测试4: 动作选择通过 ({action})")

    def test_05_update_q_value(self):
        """测试 Q 值更新"""
        rumad = RUMADController(["A", "B", "C"])
        state = "HML_H_E"
        next_state = "MML_M_M"
        action = ("A", "B")
        
        rumad.update_q_value(state, action, 0.5, next_state)
        q_value = rumad.q_table[state].get("A->B", 0.0)
        self.assertGreater(q_value, 0.0)
        print(f"[OK] 测试5: Q值更新通过 (Q={q_value:.3f})")

    def test_06_compute_reward(self):
        """测试奖励计算"""
        rumad = RUMADController(["A", "B"])
        
        prev_answers = [{"role": "A", "answer": "方案A"}, {"role": "B", "answer": "方案B"}]
        curr_answers = [{"role": "A", "answer": "详细方案A的论证"}, {"role": "B", "answer": "详细方案B的论证"}]
        
        prev_audit = {"evidence_scores": {"A": 0.5, "B": 0.5}}
        curr_audit = {"evidence_scores": {"A": 0.8, "B": 0.7}}
        
        reward = rumad.compute_reward(prev_answers, curr_answers, prev_audit, curr_audit)
        self.assertGreater(reward, 0.0)  # 质量提升应该得到正奖励
        self.assertLessEqual(reward, 1.0)
        print(f"[OK] 测试6: 奖励计算通过 (reward={reward:.3f})")

    def test_07_get_stats(self):
        """测试获取统计信息"""
        rumad = RUMADController(["A", "B", "C"])
        
        # 模拟一些操作
        state = "HML_H_E"
        rumad.q_table[state]["A->B"] = 0.5
        rumad.visit_counts[state]["A->B"] = 3
        rumad.history.append({"round": 1, "state": state, "action": ("A", "B"), "quality": 0.7})
        
        stats = rumad.get_stats()
        self.assertEqual(stats["total_actions"], 1)
        self.assertEqual(stats["q_table_size"], 1)
        self.assertEqual(stats["total_visits"], 3)
        print("[OK] 测试7: 获取统计通过")

    def test_08_enable_disable(self):
        """测试启用/禁用"""
        rumad = RUMADController(["A", "B"])
        
        rumad.disable()
        self.assertFalse(rumad.enabled)
        
        rumad.enable()
        self.assertTrue(rumad.enabled)
        print("[OK] 测试8: 启用/禁用通过")


def run_tests():
    print("=" * 60)
    print("Day 11.5 RUMAD 拓扑控制测试")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestRUMAD)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 60)
    if result.wasSuccessful():
        print("[OK] 所有测试通过！")
    else:
        print(f"[FAIL] 测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)