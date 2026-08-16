"""Implements the "compute first, phrase second" contract: pick a backend data function
based on the question, run it (deterministic, DB-backed), then hand ONLY that already-computed
JSON to the LLM to phrase into an answer. The LLM never sees raw DB rows and never computes
anything itself — see llm/prompts.py for the system prompt that enforces this on the model
side, and llm/functions.py for the data-gathering functions this module dispatches to.
"""

from sqlalchemy.orm import Session

from app.llm.client import get_llm_client
from app.llm.functions import detect_handler
from app.llm.prompts import SYSTEM_PROMPT, build_user_message


def is_ai_configured() -> bool:
    return get_llm_client().is_configured


def answer_question(db: Session, user_id: int, question: str) -> dict:
    client = get_llm_client()
    if not client.is_configured:
        return {"ai_available": False, "reply": None, "data_used": None, "error": None}

    handler = detect_handler(question)
    if handler is None:
        data = {
            "available": False,
            "reason": "This question isn't covered by the assistant's current fixed question set.",
        }
    else:
        data = handler(db, user_id, question)

    user_message = build_user_message(question, data)

    try:
        reply = client.complete(SYSTEM_PROMPT, user_message)
    except Exception as exc:  # noqa: BLE001 - external API boundary, must never crash the request
        return {"ai_available": True, "reply": None, "data_used": data, "error": f"LLM request failed: {exc}"}

    return {"ai_available": True, "reply": reply, "data_used": data, "error": None}
