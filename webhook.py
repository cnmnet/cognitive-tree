# webhook.py
import json
from fastapi import Request, HTTPException
from typing import Dict

# 模拟 Stripe / Lemon Squeezy 回调处理
# 实际使用应校验签名、解析事件，这里只做框架

async def handle_payment_webhook(request: Request) -> Dict:
    try:
        payload = await request.json()
        event_type = payload.get("type")
        data = payload.get("data", {})

        # 根据事件类型处理
        if event_type == "checkout.session.completed":
            # 完成支付，升级用户 tier
            customer_email = data.get("object", {}).get("customer_email")
            # 这里需要根据 email 查找用户并升级
            # 由于我们没有用户邮箱系统，简化：通过 metadata 传递 username
            metadata = data.get("object", {}).get("metadata", {})
            username = metadata.get("username")
            if username:
                from auth import update_user_tier
                success = update_user_tier(username, "pro")
                return {"status": "success", "user": username, "upgraded": success}
        return {"status": "ignored", "event": event_type}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook 处理失败: {e}")