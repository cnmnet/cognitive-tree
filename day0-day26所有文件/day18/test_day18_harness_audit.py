#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 18 测试：Harness 分解审计持续化 + 定义自检断言升级 + 用户态状态断言

测试内容：
1. LayerAuditService 核心功能
2. 层级贡献报告生成
3. 认知连续性计算
4. 组件完整性检查
5. 健康评分计算
6. 建议生成
7. 后台服务启动/停止
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# ===== 修复：移除不存在的导入项 =====
from crystal_tree_all_in_one_day import (
    FileIO, Config, AIClient, CrystalEngine,
    LayerAuditService, LayerContribution, AuditReport
)


def test_layer_audit_service_init():
    """测试：LayerAuditService 初始化"""
    print("=" * 60)
    print("测试 1: LayerAuditService 初始化")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    assert service is not None, "服务实例化失败"
    assert hasattr(service, 'run_audit'), "缺少 run_audit 方法"
    assert hasattr(service, 'start_background'), "缺少 start_background 方法"
    assert hasattr(service, 'stop_background'), "缺少 stop_background 方法"
    assert hasattr(service, 'get_latest_report'), "缺少 get_latest_report 方法"

    print("✅ LayerAuditService 初始化成功")
    print(f"   ✅ 服务对象创建成功")
    print(f"   ✅ 方法完整性检查通过")
    print("✅ 测试 1 通过\n")
    return True


def test_run_audit():
    """测试：运行审计"""
    print("=" * 60)
    print("测试 2: 运行审计 (run_audit)")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    print("📊 执行审计中...")
    report = service.run_audit()

    # 验证报告结构
    assert report is not None, "报告为空"
    assert hasattr(report, 'timestamp'), "缺少 timestamp"
    assert hasattr(report, 'layers'), "缺少 layers"
    assert hasattr(report, 'health_score'), "缺少 health_score"
    assert hasattr(report, 'components_status'), "缺少 components_status"
    assert hasattr(report, 'cognitive_continuity_score'), "缺少 cognitive_continuity_score"
    assert hasattr(report, 'fingerprint_change_rate'), "缺少 fingerprint_change_rate"
    assert hasattr(report, 'recommendations'), "缺少 recommendations"

    print(f"📊 审计完成")
    print(f"   ✅ 时间戳: {report.timestamp}")
    print(f"   ✅ 健康评分: {report.health_score}/10")
    print(f"   ✅ 总晶体数: {report.total_crystals}")
    print(f"   ✅ 认知连续性: {report.cognitive_continuity_score}/10")
    print(f"   ✅ 指纹变化率: {report.fingerprint_change_rate:.3f}")
    print(f"   ✅ 建议数: {len(report.recommendations)}")

    # 检查层级数据
    for layer in report.layers:
        print(f"   📊 {layer.layer_name}: {layer.crystal_count}条, 贡献 {layer.contribution_percent}%, 趋势 {layer.trend}")

    assert len(report.layers) >= 2, "层级数据不足"
    assert 0 <= report.health_score <= 10, "健康评分超出范围"

    print("✅ 测试 2 通过\n")
    return True


def test_audit_report_save():
    """测试：审计报告保存"""
    print("=" * 60)
    print("测试 3: 审计报告保存")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    # 运行审计
    report = service.run_audit()
    service._save_state(report)

    # 验证文件存在
    report_path = Config.DATA_ROOT / "系统日志" / "层级贡献报告.json"
    assert report_path.exists(), "报告文件未创建"

    # 验证文件内容
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "last_audit" in data, "缺少 last_audit"
    assert "history" in data, "缺少 history"
    assert "latest" in data, "缺少 latest"

    print(f"✅ 报告已保存: {report_path}")
    print(f"   ✅ last_audit: {data.get('last_audit')}")
    print(f"   ✅ history 数量: {len(data.get('history', []))}")
    print("✅ 测试 3 通过\n")
    return True


def test_get_latest_report():
    """测试：获取最新报告"""
    print("=" * 60)
    print("测试 4: 获取最新报告")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    # 先运行审计生成报告
    service.run_audit()

    # 获取最新报告
    latest = service.get_latest_report()
    assert latest is not None, "最新报告为空"

    print(f"✅ 最新报告获取成功")
    print(f"   ✅ 健康评分: {latest.get('health_score', 0)}/10")
    print(f"   ✅ 总晶体数: {latest.get('total_crystals', 0)}")
    print(f"   ✅ 认知连续性: {latest.get('cognitive_continuity_score', 0)}/10")

    # 检查层级
    layers = latest.get('layers', [])
    for layer in layers:
        print(f"   📊 {layer.get('layer_name')}: {layer.get('crystal_count')}条, 贡献 {layer.get('contribution_percent')}%")

    assert len(layers) >= 2, "层级数据不足"
    print("✅ 测试 4 通过\n")
    return True


def test_components_check():
    """测试：组件完整性检查"""
    print("=" * 60)
    print("测试 5: 组件完整性检查")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    # 直接调用内部方法
    components = service._check_components()

    print("📊 组件检查结果:")
    for comp, ok in components.items():
        status = "✅" if ok else "❌"
        print(f"   {status} {comp}")

    # 至少应该有 CrystalEngine 和 MetaLayer
    assert components.get("CrystalEngine", False), "CrystalEngine 不可用"
    assert components.get("MetaLayer", False), "MetaLayer 不可用"
    assert components.get("CheapGate", False), "CheapGate 不可用"

    ok_count = sum(1 for v in components.values() if v)
    assert ok_count >= 3, f"组件完整性不足，只有 {ok_count} 个可用"

    print(f"✅ 组件完整性检查通过 ({ok_count}/4 个组件可用)")
    print("✅ 测试 5 通过\n")
    return True


def test_cognitive_continuity():
    """测试：认知连续性计算"""
    print("=" * 60)
    print("测试 6: 认知连续性计算")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    score, rate = service._calculate_cognitive_continuity()

    print(f"📊 认知连续性:")
    print(f"   ✅ 评分: {score:.1f}/10")
    print(f"   ✅ 变化率: {rate:.3f}")

    assert 0 <= score <= 10, "评分超出范围"
    assert 0 <= rate <= 1, "变化率超出范围"

    print("✅ 测试 6 通过\n")
    return True


def test_health_score_calculation():
    """测试：健康评分计算"""
    print("=" * 60)
    print("测试 7: 健康评分计算")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    # 创建测试数据
    layers = [
        LayerContribution(
            layer_name="L1",
            crystal_count=10,
            contribution_percent=50.0,
            trend="up",
            trend_value=10.0,
            heat_avg=0.8,
            last_updated=datetime.now().isoformat()
        ),
        LayerContribution(
            layer_name="L2",
            crystal_count=6,
            contribution_percent=30.0,
            trend="stable",
            trend_value=0.0,
            heat_avg=0.5,
            last_updated=datetime.now().isoformat()
        ),
        LayerContribution(
            layer_name="L3",
            crystal_count=4,
            contribution_percent=20.0,
            trend="down",
            trend_value=5.0,
            heat_avg=0.3,
            last_updated=datetime.now().isoformat()
        )
    ]
    components = {"CrystalEngine": True, "DebateEngine": True, "MetaLayer": True, "CheapGate": True}
    continuity_score = 8.0

    score = service._calculate_health_score(layers, components, continuity_score)

    print(f"📊 健康评分计算:")
    print(f"   ✅ 评分: {score:.1f}/10")
    print(f"   ✅ 期望范围: 5-10（平衡分布 + 全组件 + 高连续性）")

    assert 5 <= score <= 10, f"评分 {score} 不在期望范围内"

    print("✅ 测试 7 通过\n")
    return True


def test_recommendations_generation():
    """测试：建议生成"""
    print("=" * 60)
    print("测试 8: 建议生成")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    # 创建测试数据
    layers = [
        LayerContribution(
            layer_name="L1",
            crystal_count=5,
            contribution_percent=20.0,
            trend="down",
            trend_value=10.0,
            heat_avg=0.3,
            last_updated=datetime.now().isoformat()
        ),
        LayerContribution(
            layer_name="L2",
            crystal_count=10,
            contribution_percent=40.0,
            trend="up",
            trend_value=5.0,
            heat_avg=0.5,
            last_updated=datetime.now().isoformat()
        ),
        LayerContribution(
            layer_name="L3",
            crystal_count=10,
            contribution_percent=40.0,
            trend="stable",
            trend_value=0.0,
            heat_avg=0.4,
            last_updated=datetime.now().isoformat()
        )
    ]
    components = {"CrystalEngine": True, "DebateEngine": False, "MetaLayer": True, "CheapGate": True}
    continuity = 4.0

    recommendations = service._generate_recommendations(layers, components, continuity)

    print(f"📊 建议生成:")
    print(f"   ✅ 建议数: {len(recommendations)}")

    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec}")

    assert len(recommendations) >= 2, "建议数量不足"

    print("✅ 测试 8 通过\n")
    return True


def test_background_service():
    """测试：后台服务启动/停止"""
    print("=" * 60)
    print("测试 9: 后台服务启动/停止")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    # 启动服务
    service.start_background()
    assert service._running, "服务未启动"

    print("✅ 后台服务已启动")

    # 等待1秒
    time.sleep(1)

    # 停止服务
    service.stop_background()
    assert not service._running, "服务未停止"

    print("✅ 后台服务已停止")

    print("✅ 测试 9 通过\n")
    return True


def test_audit_history():
    """测试：审计历史记录"""
    print("=" * 60)
    print("测试 10: 审计历史记录")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    # 运行多次审计
    for i in range(3):
        report = service.run_audit()
        service._save_state(report)
        print(f"   📊 第 {i+1} 次审计完成")

    # 获取历史
    history = service.get_audit_history(limit=10)

    print(f"✅ 审计历史获取成功")
    print(f"   ✅ 历史记录数: {len(history)}")

    assert len(history) >= 3, f"历史记录不足，只有 {len(history)} 条"

    print("✅ 测试 10 通过\n")
    return True


def test_crystal_engine_audit_methods():
    """测试：CrystalEngine 审计方法"""
    print("=" * 60)
    print("测试 11: CrystalEngine 审计方法")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)

    # 测试启动审计服务
    engine.start_audit_service()
    assert hasattr(engine, '_audit_service'), "审计服务未创建"

    print("✅ 启动审计服务成功")

    # 测试运行审计
    result = engine.run_audit_now()
    assert "health_score" in result, "缺少 health_score"
    assert "total_crystals" in result, "缺少 total_crystals"
    assert "components_status" in result, "缺少 components_status"
    assert "recommendations" in result, "缺少 recommendations"

    print(f"✅ 运行审计成功")
    print(f"   ✅ 健康评分: {result['health_score']:.1f}/10")
    print(f"   ✅ 总晶体数: {result['total_crystals']}")
    print(f"   ✅ 建议数: {len(result['recommendations'])}")

    # 测试获取状态
    status = engine.get_audit_status()
    assert status.get("available"), "状态不可用"

    print("✅ 获取审计状态成功")

    # 测试停止服务
    engine.stop_audit_service()

    print("✅ 测试 11 通过\n")
    return True


def test_config_audit_settings():
    """测试：Config 审计配置"""
    print("=" * 60)
    print("测试 12: Config 审计配置")
    print("=" * 60)

    # 检查 Config.AUDIT_CONFIG 是否存在
    assert hasattr(Config, 'AUDIT_CONFIG'), "缺少 AUDIT_CONFIG"

    config = Config.AUDIT_CONFIG
    print(f"📊 审计配置:")
    print(f"   ✅ enabled: {config.get('enabled')}")
    print(f"   ✅ interval_hours: {config.get('interval_hours')}")
    print(f"   ✅ component_checks: {config.get('component_checks')}")

    # 检查关键配置项
    assert config.get("enabled") is not None, "缺少 enabled"
    assert config.get("interval_hours", 0) > 0, "interval_hours 无效"
    assert len(config.get("component_checks", [])) >= 3, "component_checks 不足"
    assert config.get("fingerprint_change_threshold", 0) > 0, "fingerprint_change_threshold 无效"

    print("✅ Config 审计配置检查通过")
    print("✅ 测试 12 通过\n")
    return True


def test_audit_report_contains_layers():
    """测试：审计报告包含层级数据"""
    print("=" * 60)
    print("测试 13: 审计报告层级数据")
    print("=" * 60)

    files = FileIO()
    ai = AIClient()
    engine = CrystalEngine(files, ai_client=ai)
    service = LayerAuditService(engine, files)

    report = service.run_audit()

    # 检查层级数据
    layer_names = [l.layer_name for l in report.layers]
    expected = ["L1", "L2", "L3"]

    for name in expected:
        assert name in layer_names, f"缺少 {name} 层级数据"

    print("✅ 所有层级数据存在")

    # 检查每个层级的贡献度总和
    total_contribution = sum(l.contribution_percent for l in report.layers)
    print(f"   ✅ 贡献度总和: {total_contribution:.1f}%")

    assert 80 <= total_contribution <= 120, f"贡献度总和异常: {total_contribution}%"

    print("✅ 测试 13 通过\n")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧠 Day 18 测试：Harness 分解审计 + 持续验证 + 状态断言")
    print("=" * 60 + "\n")

    tests = [
        ("LayerAuditService 初始化", test_layer_audit_service_init),
        ("运行审计", test_run_audit),
        ("审计报告保存", test_audit_report_save),
        ("获取最新报告", test_get_latest_report),
        ("组件完整性检查", test_components_check),
        ("认知连续性计算", test_cognitive_continuity),
        ("健康评分计算", test_health_score_calculation),
        ("建议生成", test_recommendations_generation),
        ("后台服务启动/停止", test_background_service),
        ("审计历史记录", test_audit_history),
        ("CrystalEngine 审计方法", test_crystal_engine_audit_methods),
        ("Config 审计配置", test_config_audit_settings),
        ("审计报告层级数据", test_audit_report_contains_layers),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试 {name} 异常: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print("-" * 60)

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)