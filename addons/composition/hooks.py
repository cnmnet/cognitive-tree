"""作文模块钩子：复用 harness 的大脑与压缩契约。"""

from addons.base import Hooks
from harness import CompressionContract, compress_report_with_contract


def prepare_report(question: str, debate_result: dict) -> dict:
    return {"question": question, "result": debate_result, "status": "prepared"}


def compress_report(full_report: str, ai_client=None) -> str:
    contract = CompressionContract(
        max_chars=400,
        required_sections=["结论", "理由", "下一步"],
        optional_sections=["止损"],
    )
    return compress_report_with_contract(full_report, ai_client=ai_client, contract=contract)


def record_feedback(kind: str, engine=None, crystal_ids=None, role_keys=None, reward=None) -> dict:
    if engine is None:
        return {"ok": False, "reason": "engine required"}
    rate = engine.record_hebbian_reward(
        kind,
        crystal_ids=crystal_ids,
        role_keys=role_keys,
        reward=reward,
    )
    return {"ok": True, "rate": round(rate, 3)}


def feed_evolution(payload: dict, engine=None) -> dict:
    return {"ok": True, "payload_keys": list((payload or {}).keys())}


HOOKS = Hooks(
    on_report_prepare=prepare_report,
    on_report_compressed=compress_report,
    on_user_feedback=record_feedback,
    on_evolve=feed_evolution,
)
