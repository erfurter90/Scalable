"""Backend "tools" the chat assistant can call. Each function returns a plain dict of
already-computed values — never raw model objects, never something the LLM could mistake for
data it's allowed to modify. `chat_service` picks one of these via keyword-based intent
matching (no LLM function-calling needed for the MVP's fixed question set) and hands the
result straight to the LLM as read-only context.
"""

import re
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session

from app.services import financial_service, portfolio_service, score_service

FunctionHandler = Callable[[Session, int, str], dict]


def net_worth_change(db: Session, user_id: int, question: str) -> dict:
    days = 365 if re.search(r"jahr|year", question, re.IGNORECASE) else 30
    change = financial_service.get_net_worth_change(db, user_id, days)
    if change is None:
        return {"available": False, "reason": "Not enough historical net worth data yet for this period."}
    return {"available": True, "period_days": days, **change}


def btc_allocation(db: Session, user_id: int, question: str) -> dict:
    allocation = portfolio_service.get_allocation(db, user_id)
    if allocation is None:
        return {"available": False, "reason": "No asset data recorded yet."}
    return {
        "available": True,
        "btc_percent_of_total_assets": allocation.btc_percent_of_assets,
        "btc_percent_of_investments_excl_cash": allocation.btc_percent_of_investments,
        "snapshot_date": allocation.snapshot_date.isoformat(),
    }


def cash_amount(db: Session, user_id: int, question: str) -> dict:
    snapshot = financial_service.get_current_net_worth(db, user_id)
    if snapshot is None:
        return {"available": False, "reason": "No financial data recorded yet."}
    return {
        "available": True,
        "cash_total": float(snapshot.cash_total),
        "currency": "EUR",
        "snapshot_date": snapshot.snapshot_date.isoformat(),
    }


def score_explanation(db: Session, user_id: int, question: str) -> dict:
    row, result, weights = score_service.compute_and_store_score(db)
    today_out = score_service.to_score_out(result, weights, row.score_date)

    earlier_rows = score_service.get_history(db, date_to=row.score_date - timedelta(days=1))
    previous_out = score_service.history_row_to_score_out(db, earlier_rows[-1]) if earlier_rows else None

    return {
        "available": True,
        "today": today_out.model_dump(mode="json"),
        "previous_recorded_score": previous_out.model_dump(mode="json") if previous_out else None,
    }


# Ordered: first matching pattern wins. Keep more specific patterns (e.g. "btc anteil")
# ahead of broader ones so a question mentioning both isn't misrouted.
INTENT_HANDLERS: list[tuple[re.Pattern, FunctionHandler]] = [
    (re.compile(r"btc.?(anteil|allocation)|bitcoin.?(anteil|allocation)", re.IGNORECASE), btc_allocation),
    (re.compile(r"score", re.IGNORECASE), score_explanation),
    (re.compile(r"cash|bargeld|liquid", re.IGNORECASE), cash_amount),
    (re.compile(r"vermögen|net.?worth", re.IGNORECASE), net_worth_change),
]


def detect_handler(question: str) -> FunctionHandler | None:
    for pattern, handler in INTENT_HANDLERS:
        if pattern.search(question):
            return handler
    return None
