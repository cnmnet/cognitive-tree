#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 14: evolution_log.json 格式升级迁移脚本

将旧格式升级为新格式，包含：
- failure_traces: 失败时的完整上下文
- repair_attempts: 尝试的修复方案及结果
- diagnosis: 系统自己对失败原因的判断
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crystal_tree_all_in_one_day import Config


def upgrade_evolution_log() -> Dict[str, Any]:
    """
    升级 evolution_log.json 到新格式

    Returns:
        {
            "success": bool,
            "old_events": int,
            "new_events": int,
            "upgraded_count": int,
            "backup_path": str,
            "error": str (optional)
        }
    """
    log_path = Config.DATA_ROOT / "系统日志" / "evolution_log.json"
    if not log_path.exists():
        return {
            "success": False,
            "error": f"文件不存在: {log_path}"
        }

    # 备份原文件
    backup_path = log_path.parent / f"evolution_log_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        import shutil
        shutil.copy2(log_path, backup_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"备份失败: {e}"
        }

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON 解析失败: {e}"
        }

    old_events = data.get("events", [])
    old_summary = data.get("summary", {})

    upgraded_count = 0
    new_events = []

    for event in old_events:
        new_event = event.copy()

        # 检查是否已包含新字段
        has_failure_traces = "failure_traces" in new_event
        has_repair_attempts = "repair_attempts" in new_event
        has_diagnosis = "diagnosis" in new_event

        if has_failure_traces and has_repair_attempts and has_diagnosis:
            # 已经是新格式
            new_events.append(new_event)
            continue

        # 根据事件类型补充字段
        event_type = new_event.get("event_type", "")
        details = new_event.get("details", {})

        # 为 "failure_trace" 类型事件补充完整字段
        if event_type == "failure_trace":
            if "failure_traces" not in new_event:
                new_event["failure_traces"] = details.get("failure_traces", {
                    "question": details.get("question", ""),
                    "failure_type": details.get("failure_type", "unknown"),
                    "context": details.get("context", {})
                })
            if "repair_attempts" not in new_event:
                new_event["repair_attempts"] = details.get("repair_attempts", [])
            if "diagnosis" not in new_event:
                new_event["diagnosis"] = details.get("diagnosis", "系统未生成诊断")

        # 为 "alarm" 类型事件补充字段
        elif event_type == "alarm":
            if "failure_traces" not in new_event:
                new_event["failure_traces"] = {
                    "alarm_rule": details.get("rule", ""),
                    "message": details.get("message", ""),
                    "data": details.get("data", {})
                }
            if "repair_attempts" not in new_event:
                action = details.get("action", "")
                new_event["repair_attempts"] = [{
                    "action": action,
                    "success": False,
                    "timestamp": new_event.get("timestamp", datetime.now().isoformat()),
                    "note": f"自动执行了 {action}"
                }]
            if "diagnosis" not in new_event:
                new_event["diagnosis"] = f"警报触发: {details.get('rule', 'unknown')}"

        # 为 "verification_passed" 类型事件补充字段
        elif event_type == "verification_passed":
            if "diagnosis" not in new_event:
                crystal_id = details.get("crystal_id", "")
                rules_passed = details.get("rules_passed", 0)
                rules_total = details.get("rules_total", 0)
                new_event["diagnosis"] = f"晶体 {crystal_id} 验证通过 {rules_passed}/{rules_total} 条规则"

        # 为 "crystal_added" 类型事件补充字段
        elif event_type == "crystal_added":
            if "diagnosis" not in new_event:
                crystal_id = details.get("crystal_id", "")
                new_event["diagnosis"] = f"新晶体 {crystal_id} 已添加"

        # 为其他类型补充默认字段
        else:
            if "failure_traces" not in new_event:
                new_event["failure_traces"] = {
                    "note": "非失败事件，无失败轨迹",
                    "event_type": event_type
                }
            if "repair_attempts" not in new_event:
                new_event["repair_attempts"] = []
            if "diagnosis" not in new_event:
                new_event["diagnosis"] = f"事件类型: {event_type}，无诊断信息"

        # 确保 details 中有 diagnosis 字段
        if "diagnosis" not in new_event.get("details", {}):
            new_event["details"]["diagnosis"] = new_event.get("diagnosis", "")

        new_events.append(new_event)
        upgraded_count += 1

    # 构建新数据
    new_data = {
        "events": new_events,
        "summary": old_summary,
        "version": "2.0",
        "upgraded_at": datetime.now().isoformat(),
        "total_events": len(new_events)
    }

    # 写入文件
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    return {
        "success": True,
        "old_events": len(old_events),
        "new_events": len(new_events),
        "upgraded_count": upgraded_count,
        "backup_path": str(backup_path),
        "version": "2.0"
    }


def main():
    """主函数"""
    print("=" * 60)
    print("Day 14: evolution_log.json 格式升级")
    print("=" * 60)

    result = upgrade_evolution_log()

    if result["success"]:
        print(f"✅ 升级成功!")
        print(f"   - 旧事件数: {result['old_events']}")
        print(f"   - 新事件数: {result['new_events']}")
        print(f"   - 升级事件数: {result['upgraded_count']}")
        print(f"   - 备份路径: {result['backup_path']}")
        print(f"   - 版本: {result.get('version', '2.0')}")
    else:
        print(f"❌ 升级失败: {result.get('error', '未知错误')}")

    print("=" * 60)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())