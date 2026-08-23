"""Pulls the user's full Bitvavo transaction history and replays it into deterministic
per-asset holdings (quantity + weighted-average EUR cost basis) via the shared
exchange_sync_common machinery — see that module for the exchange-agnostic replay math,
symbol mapping, and entry-replacement logic. This module only handles what's Bitvavo-specific:
its provider, its EUR-quoted markets, and its response field names.

Writes a Transaction audit row per trade/deposit/withdrawal (idempotent via the
(user_id, source, external_id) unique constraint — re-running a sync after a new Sparplan
purchase only adds the new rows) and then replaces the corresponding FinancialEntry rows so
the rest of the app (dashboard, allocation charts, gain/loss display) sees the result as an
ordinary quantity-tracked holding — no special-casing needed anywhere else.
"""

import time
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.transaction import TransactionType
from app.providers.bitvavo_provider import BitvavoProvider
from app.services.exchange_sync_common import (
    SYMBOL_TO_COINGECKO_ID,
    AssetSyncResult,
    ExchangeSyncResult,
    compute_holding,
    replace_and_create_entry,
    upsert_transaction,
)
from app.services.financial_service import recompute_net_worth_snapshot

_SOURCE = "bitvavo"
_LABEL = "Bitvavo"

# Bitvavo trades are only ever fetched for X-EUR markets here, so price/fee are always EUR
# already — no FX conversion step needed (unlike Bitget, which quotes in USDT).
_QUOTE_CURRENCY = "EUR"

# CoinGecko's free tier enforces a short burst limit -- unlike Bitget/Coinbase's sync
# services, this one had no pacing between per-coin price lookups at all, which reliably
# made every coin in a multi-holding sync fail with 429 (confirmed from a real sync where
# all 5 held coins failed, not just the ones past a burst threshold). CoinGeckoProvider now
# also retries a single 429 with backoff, but pacing the requests in the first place still
# avoids triggering it as often.
_PRICE_LOOKUP_DELAY_SECONDS = 0.5


def _ms_to_datetime(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def _fetch_transactions_for_symbol(db: Session, user_id: int, provider: BitvavoProvider, symbol: str) -> str | None:
    """Fetches and upserts all trade/deposit/withdrawal rows for one symbol. Returns an error
    message if the trades call failed. Deposit/withdrawal failures are non-fatal (trades alone
    still give a usable, if possibly `cost_basis_incomplete`-free, result)."""
    market = f"{symbol}-EUR"
    trades_result = provider.get_trades(market)
    if trades_result.status != "ok":
        return f"Trades für {market} konnten nicht geladen werden: {trades_result.error_message}"

    for trade in trades_result.data or []:
        try:
            fee = trade.get("fee") if trade.get("fee") is not None else trade.get("feePaid")
            upsert_transaction(
                db,
                user_id,
                source=_SOURCE,
                external_id=str(trade["id"]),
                type_=TransactionType.buy if trade["side"] == "buy" else TransactionType.sell,
                asset=symbol,
                amount=Decimal(str(trade["amount"])),
                price=Decimal(str(trade["price"])),
                fee=Decimal(str(fee)) if fee is not None else None,
                currency=_QUOTE_CURRENCY,
                occurred_at=_ms_to_datetime(int(trade["timestamp"])),
                raw=trade,
            )
        except (KeyError, ValueError, TypeError):
            continue  # malformed row from the API — skip rather than crash the whole sync

    deposits_result = provider.get_deposit_history(symbol)
    for deposit in (deposits_result.data or []) if deposits_result.status == "ok" else []:
        try:
            external_id = f"deposit:{deposit.get('txId') or deposit.get('paymentId') or deposit['timestamp']}"
            upsert_transaction(
                db,
                user_id,
                source=_SOURCE,
                external_id=external_id,
                type_=TransactionType.deposit,
                asset=symbol,
                amount=Decimal(str(deposit["amount"])),
                price=None,
                fee=Decimal(str(deposit["fee"])) if deposit.get("fee") is not None else None,
                currency=_QUOTE_CURRENCY,
                occurred_at=_ms_to_datetime(int(deposit["timestamp"])),
                raw=deposit,
            )
        except (KeyError, ValueError, TypeError):
            continue

    withdrawals_result = provider.get_withdrawal_history(symbol)
    for withdrawal in (withdrawals_result.data or []) if withdrawals_result.status == "ok" else []:
        try:
            external_id = f"withdrawal:{withdrawal.get('txId') or withdrawal.get('paymentId') or withdrawal['timestamp']}"
            upsert_transaction(
                db,
                user_id,
                source=_SOURCE,
                external_id=external_id,
                type_=TransactionType.withdrawal,
                asset=symbol,
                amount=Decimal(str(withdrawal["amount"])),
                price=None,
                fee=Decimal(str(withdrawal["fee"])) if withdrawal.get("fee") is not None else None,
                currency=_QUOTE_CURRENCY,
                occurred_at=_ms_to_datetime(int(withdrawal["timestamp"])),
                raw=withdrawal,
            )
        except (KeyError, ValueError, TypeError):
            continue

    db.commit()
    return None


def sync(db: Session, user_id: int) -> ExchangeSyncResult:
    provider = BitvavoProvider()
    if not provider.is_configured:
        return ExchangeSyncResult(configured=False, error="Bitvavo-API nicht konfiguriert.")

    balance_result = provider.get_balance()
    if balance_result.status != "ok":
        return ExchangeSyncResult(
            configured=True, error=f"Guthaben konnte nicht geladen werden: {balance_result.error_message}"
        )

    symbols = [
        row["symbol"]
        for row in (balance_result.data or [])
        if row.get("symbol") != "EUR"
        and (Decimal(str(row.get("available", 0))) + Decimal(str(row.get("inOrder", 0)))) > 0
    ]

    results: list[AssetSyncResult] = []
    for symbol in symbols:
        fetch_error = _fetch_transactions_for_symbol(db, user_id, provider, symbol)
        if fetch_error:
            results.append(
                AssetSyncResult(
                    symbol=symbol,
                    coingecko_id=None,
                    quantity=Decimal(0),
                    average_cost_basis=None,
                    cost_basis_incomplete=False,
                    current_value_eur=None,
                    error=fetch_error,
                )
            )
            continue

        holding = compute_holding(db, user_id, symbol, _SOURCE)
        coingecko_id = SYMBOL_TO_COINGECKO_ID.get(symbol)

        if coingecko_id is None:
            results.append(
                AssetSyncResult(
                    symbol=symbol,
                    coingecko_id=None,
                    quantity=holding.quantity,
                    average_cost_basis=holding.average_cost_basis,
                    cost_basis_incomplete=holding.cost_basis_incomplete,
                    current_value_eur=None,
                    note=(
                        f"Kein CoinGecko-Mapping für '{symbol}' hinterlegt — Transaktionen wurden "
                        "aufgezeichnet, aber kein Eintrag angelegt/ersetzt."
                    ),
                )
            )
            continue

        time.sleep(_PRICE_LOOKUP_DELAY_SECONDS)
        replaced_labels, current_value_eur, error = replace_and_create_entry(
            db, user_id, source=_SOURCE, label=_LABEL, symbol=symbol, holding=holding, coingecko_id=coingecko_id
        )
        results.append(
            AssetSyncResult(
                symbol=symbol,
                coingecko_id=coingecko_id,
                quantity=holding.quantity,
                average_cost_basis=holding.average_cost_basis,
                cost_basis_incomplete=holding.cost_basis_incomplete,
                current_value_eur=current_value_eur,
                replaced_entry_labels=replaced_labels,
                error=error,
            )
        )

    recompute_net_worth_snapshot(db, user_id)
    return ExchangeSyncResult(configured=True, assets=results)
