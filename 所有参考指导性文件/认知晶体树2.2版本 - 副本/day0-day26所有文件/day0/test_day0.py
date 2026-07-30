#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day 0 验收测试"""

import sys
import os
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crystal_tree_all_in_one import Config, FileIO

def test_day0():
    print("🔍 开始 Day 0 验收测试...")
    errors = []

    # 1. 检查双基线诊断报告是否存在
    report_json = Config.DATA_ROOT / "系统日志" / "双基线诊断报告.json"
    report_md = Config.DATA_ROOT / "系统日志" / "双基线诊断报告.md"
    if not report_json.exists():
        errors.append("双基线诊断报告.json 不存在")
    else:
        with open(report_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "summary" not in data or "analysis" not in data:
            errors.append("诊断报告结构不完整")
        else:
            print("✅ 双基线诊断报告存在且格式正确")

    if not report_md.exists():
        errors.append("双基线诊断报告.md 不存在")
    else:
        print("✅ Markdown版报告存在")

    # 2. 检查灵感池.json
    insp_path = Config.DATA_ROOT / "系统日志" / "灵感池.json"
    if not insp_path.exists():
        errors.append("灵感池.json 不存在")
    else:
        with open(insp_path, "r", encoding="utf-8") as f:
            insp = json.load(f)
        if not isinstance(insp, list) or not insp:
            errors.append("灵感池格式错误或为空")
        else:
            found_insp001 = any(item.get("id") == "INSP-001" for item in insp)
            if not found_insp001:
                errors.append("未找到 INSP-001")
            else:
                print("✅ 灵感池.json 存在且包含 INSP-001")

    # 3. 检查 pareto_frontier.json
    pareto_path = Config.DATA_ROOT / "系统日志" / "pareto_frontier.json"
    if not pareto_path.exists():
        errors.append("pareto_frontier.json 不存在")
    else:
        with open(pareto_path, "r", encoding="utf-8") as f:
            pareto = json.load(f)
        if "configs" not in pareto or "history" not in pareto:
            errors.append("pareto_frontier.json 结构不完整")
        else:
            print("✅ pareto_frontier.json 存在")

    # 4. 检查埋点数据（至少初始化过）
    metrics_path = Config.DATA_ROOT / "系统日志" / "埋点数据.json"
    if not metrics_path.exists():
        # 可能尚未生成，不报错，但提示
        print("⚠️ 埋点数据尚未生成（运行几次对话后会自动记录）")
    else:
        print("✅ 埋点数据文件存在")

    # 5. 检查自检断言（通过运行主文件时已执行，此处检查代码中是否有相关逻辑）
    # 简单检查主文件中是否有自检代码
    main_file = Path(__file__).parent / "crystal_tree_all_in_one.py"
    if main_file.exists():
        content = main_file.read_text(encoding="utf-8")
        if "认知晶体树2.2定义自检断言" in content:
            print("✅ 主文件包含自检断言代码")
        else:
            errors.append("主文件中未找到自检断言代码")

    if errors:
        print("❌ 验收失败，以下问题需修复:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("🎉 Day 0 验收全部通过！")
        return True

if __name__ == "__main__":
    success = test_day0()
    sys.exit(0 if success else 1)