#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 21 认证与付费门控测试
用法：
    python test_day21.py --module      # 测试 auth 模块（无需启动服务）
    python test_day21.py --api         # 测试 Web API（需要先启动服务）
    python test_day21.py --help        # 显示帮助
"""
import sys
sys.path.insert(0, '.')
import json
import time
import argparse
import subprocess
import requests
from typing import Optional

# 确保可以导入 auth 模块（假设当前目录在项目根）
try:
    import auth
except ImportError:
    print("错误：无法导入 auth 模块，请确保在项目根目录运行。")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8788"   # 默认服务地址
TEST_USERNAME = "testuser"
TEST_PASSWORD = "password123"


def test_auth_module():
    """直接测试 auth 模块（不依赖网络）"""
    print("\n=== 测试 auth 模块 ===")

    # 1. 注册
    ok, msg = auth.register_user(TEST_USERNAME, TEST_PASSWORD)
    print(f"注册: {msg}")
    if not ok:
        # 如果用户已存在，我们继续
        print("用户可能已存在，继续测试...")

    # 2. 登录
    ok, msg, token = auth.login_user(TEST_USERNAME, TEST_PASSWORD)
    print(f"登录: {msg}, token={token[:20] if token else 'None'}...")
    assert token is not None, "登录失败"

    # 3. 获取用户信息
    user = auth.get_user(TEST_USERNAME)
    print(f"用户信息: tier={user.tier}, trial_used={user.trial_used}")
    assert user.tier == "free"

    # 4. 消耗试用次数
    for i in range(3):
        remaining = auth.get_trial_remaining(TEST_USERNAME)
        print(f"第{i+1}次调用前剩余次数: {remaining}")
        ok = auth.increment_trial(TEST_USERNAME)
        print(f"  消耗后: {ok}, 剩余: {auth.get_trial_remaining(TEST_USERNAME)}")

    # 5. 升级到 pro
    ok = auth.update_user_tier(TEST_USERNAME, "pro")
    print(f"升级到 pro: {ok}")
    user = auth.get_user(TEST_USERNAME)
    print(f"升级后 tier: {user.tier}")
    assert user.tier == "pro"

    # 6. 升级后试用次数不受限
    ok = auth.increment_trial(TEST_USERNAME)
    print(f"升级后调用: {ok}, 剩余: {auth.get_trial_remaining(TEST_USERNAME)}")
    assert ok is True

    print("✅ auth 模块测试通过！")


def test_api():
    """测试 Web API（需服务已启动）"""
    print("\n=== 测试 Web API（需服务运行于 %s） ===" % BASE_URL)

    # 检查服务是否可用
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=3)
        if resp.status_code != 200:
            print("服务未响应或状态异常，请先启动服务：")
            print("  python crystal_tree_all_in_one_day.py --web")
            sys.exit(1)
    except requests.ConnectionError:
        print("无法连接到服务，请先启动服务：")
        print("  python crystal_tree_all_in_one_day.py --web")
        sys.exit(1)

    session = requests.Session()

    # 1. 注册
    reg_resp = session.post(f"{BASE_URL}/api/auth/register", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    })
    print(f"注册响应: {reg_resp.json()}")

    # 2. 登录
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    })
    login_data = login_resp.json()
    print(f"登录响应: {login_data}")
    token = login_data.get("token")
    assert token, "登录失败，无 token"

    # 设置认证头
    session.headers.update({"Authorization": f"Bearer {token}"})

    # 3. 获取用户信息
    me_resp = session.get(f"{BASE_URL}/api/auth/me")
    me_data = me_resp.json()
    print(f"用户信息: {me_data}")
    assert me_data["tier"] == "free"

    # 4. 模拟调用深度推理（消耗试用次数）
    # 注意：深度推理需要 session_id，我们可以先创建一个会话
    sess_resp = session.post(f"{BASE_URL}/api/sessions", json={"name": "test_session"})
    session_id = sess_resp.json().get("id")
    assert session_id, "创建会话失败"

    # 先调用几次，观察次数变化
    for i in range(3):
        deep_resp = session.post(f"{BASE_URL}/api/deep-reasoning", json={
            "session_id": session_id,
            "input": f"测试问题 {i+1}",
            "mode": "auto",
            "max_rounds": 2
        })
        if deep_resp.status_code == 403:
            print(f"第{i+1}次调用返回403: {deep_resp.json()}")
            break
        else:
            print(f"第{i+1}次调用成功，状态码 {deep_resp.status_code}")
        # 查询剩余次数
        me_resp = session.get(f"{BASE_URL}/api/auth/me")
        remaining = me_resp.json().get("trial_remaining")
        print(f"当前剩余试用次数: {remaining}")

    # 5. 升级用户（模拟 webhook）
    # 直接调用 auth.update_user_tier（或通过 webhook 接口）
    # 这里我们直接调用模块函数，模拟支付成功
    ok = auth.update_user_tier(TEST_USERNAME, "pro")
    print(f"升级用户: {ok}")

    # 6. 再次调用深度推理，应不再限制
    me_resp = session.get(f"{BASE_URL}/api/auth/me")
    me_data = me_resp.json()
    print(f"升级后用户信息: {me_data}")
    assert me_data["tier"] == "pro"

    deep_resp = session.post(f"{BASE_URL}/api/deep-reasoning", json={
        "session_id": session_id,
        "input": "升级后测试问题",
        "mode": "auto",
        "max_rounds": 2
    })
    print(f"升级后调用响应码: {deep_resp.status_code}")
    assert deep_resp.status_code != 403, "升级后仍被限制"

    print("✅ API 测试通过！")


def main():
    parser = argparse.ArgumentParser(description="Day 21 测试")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--module", action="store_true", help="测试 auth 模块")
    group.add_argument("--api", action="store_true", help="测试 Web API（需启动服务）")
    args = parser.parse_args()

    if args.module:
        test_auth_module()
    elif args.api:
        test_api()
    else:
        parser.print_help()
        print("\n提示：请使用 --module 或 --api 指定测试模式。")


if __name__ == "__main__":
    main()