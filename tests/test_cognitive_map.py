import requests
import json

def test_cognitive_map_api():
    url = "http://127.0.0.1:8788/api/cognitive-map"
    try:
        resp = requests.get(url)
        data = resp.json()
        print("状态码:", resp.status_code)
        print("响应状态:", data.get("status"))
        if data.get("status") == "success":
            nodes = data.get("nodes", [])
            blind = data.get("blind_spots", [])
            print(f"节点数: {len(nodes)}")
            print(f"盲区数: {len(blind)}")
            if nodes:
                sample = nodes[0]
                print("示例节点:", json.dumps(sample, indent=2, ensure_ascii=False)[:300])
            print("✅ API 测试通过")
        else:
            print("❌ API 返回错误:", data.get("message"))
    except Exception as e:
        print("❌ 请求失败:", e)

if __name__ == "__main__":
    test_cognitive_map_api()