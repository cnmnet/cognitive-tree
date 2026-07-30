import requests
import json
import time
import sys
from pathlib import Path

# ===== 配置 =====
BASE_URL = "http://127.0.0.1:8788"
DEEPSEEK_API_KEY = "sk-dbe3d0f5e72f46559f24f9d61e6b5975"  # 替换为您的真实Key
TEST_USER = "康迈乐"
TEST_PASS = "a123456"

# ===== PR 列表（使用您提供的两个有效PR + 之前已成功的PR） =====
PR_SOURCES = [
    ("pr1", "https://github.com/langchain-ai/langchain/pull/34570.diff"),  # 已成功
    ("pr2", "https://github.com/langchain-ai/langchain/pull/39057.diff"),  # 新增有效
    ("pr3", "https://github.com/langchain-ai/langchain/pull/38806.diff"),  # 新增有效
]


# ===== 认证 =====
def get_token():
    # 注册（若已存在则忽略）
    requests.post(f"{BASE_URL}/api/auth/register", 
                  json={"username": TEST_USER, "password": TEST_PASS})
    # 登录获取Token
    resp = requests.post(f"{BASE_URL}/api/auth/login", 
                         json={"username": TEST_USER, "password": TEST_PASS})
    if resp.status_code != 200:
        print(f"❌ 登录失败: {resp.text}")
        sys.exit(1)
    token = resp.json().get("token")
    if not token:
        print("❌ 未获取到Token")
        sys.exit(1)
    return token


# ===== 下载diff内容 =====
def fetch_diff(url):
    resp = requests.get(url)
    if resp.status_code != 200:
        return None, f"下载失败: HTTP {resp.status_code}"
    content = resp.text
    if not content.strip() or "diff --git" not in content:
        return None, "下载内容无效（不包含diff信息）"
    return content, None


# ===== 提交PR审计任务 =====
def submit_pr_audit(token, diff_content, session_id):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "session_id": session_id,
        "input": diff_content,
        "mode": "pr_review",
        "max_rounds": 2,
        "api_key": DEEPSEEK_API_KEY
    }
    resp = requests.post(f"{BASE_URL}/api/deep-reasoning", json=payload, headers=headers)
    if resp.status_code != 200:
        return None, f"提交失败: {resp.text}"
    job_id = resp.json().get("job_id")
    if not job_id:
        return None, "未返回job_id"
    return job_id, None


# ===== 轮询任务状态 =====
def poll_job(token, job_id, timeout=180, interval=3):
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=headers)
        if resp.status_code != 200:
            print(f"  ⚠️ 获取状态失败: {resp.status_code}")
            time.sleep(interval)
            continue
        data = resp.json()
        status = data.get("status")
        progress = data.get("progress", 0)
        print(f"  ⏳ 进度: {progress}% (状态: {status})")

        if status == "done":
            return data.get("result"), None
        elif status in ("error", "failed"):
            return None, data.get("error", "任务失败")
        time.sleep(interval)
    return None, "等待超时"


# ===== 提取pr_comment =====
def extract_pr_comment(result):
    if not result:
        return None
    if isinstance(result, dict):
        # 直接提取
        pr_comment = result.get("pr_comment")
        if pr_comment:
            return pr_comment
        # 嵌套在result中
        if "result" in result and isinstance(result["result"], dict):
            pr_comment = result["result"].get("pr_comment")
            if pr_comment:
                return pr_comment
        # 在summary中
        summary = result.get("summary")
        if isinstance(summary, dict):
            pr_comment = summary.get("pr_comment")
            if pr_comment:
                return pr_comment
    return None


# ===== 主流程 =====
def main():
    print("🔐 正在认证...")
    token = get_token()
    print("✅ 认证成功")

    for name, url in PR_SOURCES:
        print(f"\n{'='*60}")
        print(f"📥 处理 {name}: {url}")
        print(f"{'='*60}")

        # 1. 下载diff
        diff_content, err = fetch_diff(url)
        if err:
            print(f"❌ {err}")
            continue
        print(f"✅ diff下载成功 ({len(diff_content)} 字符)")

        # 2. 提交任务
        job_id, err = submit_pr_audit(token, diff_content, f"pr_{name}")
        if err:
            print(f"❌ {err}")
            continue
        print(f"📋 任务ID: {job_id}")

        # 3. 等待完成
        result, err = poll_job(token, job_id)
        if err:
            print(f"❌ {err}")
            continue

        # 4. 提取并保存
        pr_comment = extract_pr_comment(result)
        if pr_comment:
            output_file = f"PR_COMMENT_{name}.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(pr_comment)
            print(f"✅ 报告已保存: {output_file}")
            # 预览前几行
            lines = pr_comment.split("\n")[:8]
            print(f"📄 预览:\n" + "\n".join(lines) + "\n...")
        else:
            print("⚠️ 未找到pr_comment，完整结果:")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])

    print(f"\n{'='*60}")
    print("✅ 全部处理完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()