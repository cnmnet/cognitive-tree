#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 22 集成测试 - 灵感熔炉复盘（二）
独立运行，验证：
1. 待筛选灵感被正确评估（L2筛选）
2. S/A级灵感自动执行（生成晶体或任务卡片）
3. 已执行灵感补充闭环反馈
4. 中期报告生成
5. 进化日志记录执行事件
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from crystal_tree_all_in_one_day import (
        Config, FileIO, AIClient, CrystalEngine, MetaLayer,
        TaskCard, datetime, json, Path
    )
except ImportError as e:
    print(f"❌ 无法导入核心模块：{e}")
    print("请确保 'crystal_tree_all_in_one_day.py' 在当前目录，且已添加 Day 22 的方法。")
    sys.exit(1)


def prepare_test_inspiration_pool():
    """
    准备测试用的灵感池数据。
    修改内容：加入高价值灵感，确保至少有一条能达到 S 级。
    """
    insp_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
    insp_path.parent.mkdir(parents=True, exist_ok=True)

    # 若文件存在且不为空，读取现有数据，否则初始化空列表
    if insp_path.exists() and insp_path.stat().st_size > 10:
        try:
            with open(insp_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list) and len(existing) > 0:
                print("✅ 已存在灵感池数据，将追加测试条目（避免覆盖）")
                inspirations = existing
            else:
                inspirations = []
        except:
            inspirations = []
    else:
        inspirations = []

    # ===== 定义测试灵感（重点：包含高重要性关键词，长度适中） =====
    test_items = [
        {
            "id": "INSP-TEST-001",
            "source": "测试用例",
            "content": "核心突破：基于注意力机制的上下文压缩系统，可提升长文本处理效率并优化认知负载。",
            "status": "待筛选",
            "created_at": datetime.now().isoformat()
        },
        {
            "id": "INSP-TEST-002",
            "source": "测试用例",
            "content": "战略框架：建立晶体自动老化机制，定期归档低热度晶体，保持知识新鲜度与系统活力。",
            "status": "待筛选",
            "created_at": datetime.now().isoformat()
        },
        {
            "id": "INSP-TEST-003",
            "source": "测试用例",
            "content": "创新系统：设计一个‘认知体检’功能，每周自动检查知识结构健康度，提供修复建议。",
            "status": "待筛选",
            "created_at": datetime.now().isoformat()
        },
        # 专门设计一条 S 级灵感（高重要性、紧急性、一致性）
        {
            "id": "INSP-TEST-S001",
            "source": "测试用例",
            "content": "范式变革：构建跨领域知识迁移的认知晶体网络，使系统能自动发现并填补知识盲区，从根本上提升决策质量。",
            "status": "待筛选",
            "created_at": datetime.now().isoformat()
        }
    ]

    existing_ids = {item.get("id") for item in inspirations}
    added_count = 0
    for item in test_items:
        if item["id"] not in existing_ids:
            inspirations.append(item)
            added_count += 1
            existing_ids.add(item["id"])

    if added_count > 0:
        print(f"✅ 新增 {added_count} 条测试灵感（含一条高价值灵感）")

    # 写回文件
    with open(insp_path, "w", encoding="utf-8") as f:
        json.dump(inspirations, f, ensure_ascii=False, indent=2)

    return insp_path


def run_test():
    """
    执行完整的 Day 22 测试流程。
    """
    print("=" * 70)
    print("🧪 Day 22 集成测试：灵感熔炉复盘（二）")
    print("=" * 70)

    # ---- 1. 准备测试数据 ----
    print("\n📂 准备测试灵感池...")
    insp_path = prepare_test_inspiration_pool()
    print(f"   灵感池文件：{insp_path}")

    # ---- 2. 初始化系统组件 ----
    print("\n🔧 初始化系统组件...")
    files = FileIO()
    ai_client = AIClient()
    engine = CrystalEngine(files, ai_client=ai_client)
    meta = engine.meta

    # 检查方法是否存在
    if not hasattr(meta, "inspiration_furnace_review_phase2"):
        print("\n❌ 错误：MetaLayer 缺少 inspiration_furnace_review_phase2 方法！")
        print("   请先按照 Day 22 修改说明，在 MetaLayer 中添加该方法。")
        sys.exit(1)

    # ---- 3. 运行二阶段复盘 ----
    print("\n🚀 执行灵感熔炉复盘（二）...")
    start_time = time.time()
    try:
        result = meta.inspiration_furnace_review_phase2()
    except Exception as e:
        print(f"\n❌ 执行过程中抛出异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    elapsed = time.time() - start_time

    # ---- 4. 输出执行结果 ----
    print("\n📊 执行结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    # ---- 5. 打印每条灵感的评估详情（调试用） ----
    print("\n🔍 灵感的评估详情：")
    try:
        with open(insp_path, "r", encoding="utf-8") as f:
            all_insp = json.load(f)
        for insp in all_insp:
            eval_data = insp.get("evaluation", {})
            level = eval_data.get("level", "未评估")
            score = eval_data.get("total_score", 0)
            print(f"  {insp.get('id')} | 等级: {level} | 总分: {score:.2f} | 内容: {insp.get('content')[:40]}...")
    except Exception as e:
        print(f"   ⚠️ 读取灵感池详情失败：{e}")

    # ---- 6. 验证关键点 ----
    print("\n🔍 验证关键点：")

    # 6.1 是否有执行记录
    executed_count = result.get("executed_count", 0)
    if executed_count > 0:
        print(f"   ✅ 成功执行 {executed_count} 条 S/A 级灵感")
    else:
        print("   ⚠️ 没有 S/A 级灵感被自动执行（可能待筛选灵感不足或评分未达标）")
        print("   💡 提示：请检查灵感池中是否有待筛选灵感，并确认评估逻辑是否合理。")

    # 6.2 中期报告是否生成
    report_path = Config.DATA_ROOT / "系统日志" / "灵感熔炉中期报告.json"
    if report_path.exists():
        print(f"   ✅ 中期报告已生成：{report_path}")
        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        print(f"      报告摘要：{report_data.get('summary', '')}")
        success_rate = report_data.get("execution_success_rate", 0)
        if success_rate >= 0.8:
            print(f"   ✅ 执行成功率：{success_rate:.0%}（良好）")
        else:
            print(f"   ⚠️ 执行成功率：{success_rate:.0%}（偏低，可能有未闭环的已执行项）")
    else:
        print("   ❌ 中期报告未生成！")

    # 6.3 进化日志是否记录
    log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)
        events = log_data.get("events", [])
        exec_events = [e for e in events if e.get("event_type") == "inspiration_executed"]
        print(f"   📝 进化日志中有 {len(exec_events)} 条灵感执行记录")
        if exec_events:
            latest = exec_events[-1]
            print(f"      最新记录：{latest.get('details', {}).get('inspiration_id')} -> {latest.get('details', {}).get('target_id')}")
    else:
        print("   ⚠️ 未找到进化日志文件，可能未记录执行事件")

    # ---- 7. 显示灵感池状态 ----
    print("\n📋 当前灵感池状态（摘要）：")
    try:
        with open(insp_path, "r", encoding="utf-8") as f:
            all_insp = json.load(f)
        status_count = {}
        for insp in all_insp:
            st = insp.get("status", "未知")
            status_count[st] = status_count.get(st, 0) + 1
        print(f"   状态分布：{status_count}")
        executed = [i for i in all_insp if i.get("status") == "已执行"]
        if executed:
            print("   最近已执行的灵感（最多3条）：")
            for i in executed[-3:]:
                print(f"     - {i.get('id')} -> {i.get('result', {}).get('target_id', '无目标')}")
    except Exception as e:
        print(f"   ⚠️ 读取灵感池失败：{e}")

    # ---- 8. 测试结果总结 ----
    print("\n" + "=" * 70)
    if executed_count > 0 and report_path.exists():
        print("✅ 所有测试通过！Day 22 任务完成。")
    else:
        print("⚠️ 部分验证未通过，请检查日志和报告。")
        print("   如果依然没有执行，建议手动运行一次评估，或调整阈值（见代码注释）。")
    print(f"⏱ 总耗时：{elapsed:.2f} 秒")
    print("=" * 70)


if __name__ == "__main__":
    run_test()