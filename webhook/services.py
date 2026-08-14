"""?????"""

from __future__ import annotations

from typing import Any, Dict


def create_checkout_session(config: Any, stripe: Any, username: str) -> Dict[str, Any]:
    if not config.STRIPE_SECRET_KEY:
        raise ValueError("Stripe 未配置")
    stripe.api_key = config.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": config.STRIPE_PRICE_ID, "quantity": 1}],
        mode="subscription",
        success_url="http://localhost:8788/success",
        cancel_url="http://localhost:8788/cancel",
        metadata={"username": username},
    )
    return {"session_id": session.id, "url": session.url}
