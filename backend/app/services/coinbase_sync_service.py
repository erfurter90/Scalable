"""Pulls the user's full Coinbase (Advanced Trade) transaction history and replays it into
deterministic per-asset holdings via the shared exchange_sync_common machinery — see that
module for the exchange-agnostic replay math, symbol mapping, and entry-replacement logic.

Coinbase-specific:
- The quote currency comes from the `product_id` suffix (e.g. "ETH-EUR" -> quote "EUR",
  "ETH-USD" -> quote "USD") rather than being fixed the way Bitvavo's markets are always EUR
  or Bitget's are always USDT — Coinbase lets EU users trade directly against EUR. USD-quoted
  fills are converted via the app's existing USD/EUR rate; any other quote currency is skipped
  rather than guessed, mirroring the EUR/USD-only rule already enforced in
  `financial_service._convert_purchase_price_to_eur`.
- `/orders/historical/fills` and `/accounts` are both cursor-paginated (`cursor`/`has_next`),
  not date-windowed — paged through unconditionally until `has_next` is false, same
  "never assume a lookback limit, verify against a real account" lesson learned building the
  Bitget integration.
- The same quantity-reconciliation safety net as Bitget applies: if the replayed ledger
  disagrees with Coinbase's own reported balance for a coin (e.g. a position whose origin
  predates what the fills history covers), the real balance wins for *quantity* and the cost
  basis is dropped rather than shown as if it were exact.
"""

import time
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.market_data import DataPointStatus
from app.models.transaction import TransactionType
from app.providers.coinbase_provider import CoinbaseProvider
from app.services import market_data_service
from app.services.exchange_sync_common import (
    SYMBOL_TO_COINGECKO_ID,
    AssetHolding,
    AssetSyncResult,
    ExchangeSyncResult,
    compute_holding,
    replace_and_create_entry,
    upsert_transaction,
)
from app.services.financial_service import recompute_net_worth_snapshot

_SOURCE = "coinbase"
_LABEL = "Coinbase"
_SUPPORTED_QUOTES = {"EUR", "USD"}
_QUANTITY_MISMATCH_RELATIVE_TOLERANCE = Decimal("0.005")
_PAGE_DELAY_SECONDS = 0.5
_MAX_PAGE_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 1.5
_PRICE_LOOKUP_DELAY_SECONDS = 0.5  # pacing between per-coin CoinGecko price lookups


def _get_usd_eur_rate(db: Session) -> Decimal | None:
    rate_point = market_data_service.get_fresh(db, "fx_usd_eur")
    if rate_point.status != DataPointStatus.ok or rate_point.value is None:
        return None
    return Decimal(str(rate_point.value))


def _quote_to_eur(amount: Decimal, quote: str, usd_eur_rate: Decimal) -> Decimal:
    if quote == "EUR":
        return amount
    return (amount * usd_eur_rate).quantize(Decimal("0.01"))


def _parse_product(product_id: str) -> tuple[str, str] | None:
    """"ETH-EUR" -> ("ETH", "EUR"). None if the id isn't a plain BASE-QUOTE pair."""
    parts = product_id.split("-")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def _parse_trade_datetime(trade_time: str) -> datetime:
    # Coinbase timestamps are ISO 8601 (e.g. "2024-07-05T12:34:56.789Z").
    return datetime.fromisoformat(trade_time.replace("Z", "+00:00"))


def _account_quantity(account: dict) -> Decimal:
    try:
        available = Decimal(str(account.get("available_balance", {}).get("value", "0")))
    except (InvalidOperation, TypeError):
        available = Decimal(0)
    try:
        hold = Decimal(str(account.get("hold", {}).get("value", "0")))
    except (InvalidOperation, TypeError):
        hold = Decimal(0)
    return available + hold


def _fetch_all_accounts(provider: CoinbaseProvider) -> tuple[list[dict], str | None]:
    accounts: list[dict] = []
    cursor: str | None = None
    while True:
        result = provider.get_accounts(cursor=cursor)
        if result.status != "ok":
            return accounts, f"Guthaben konnte nicht vollständig geladen werden: {result.error_message}"
        data = result.data or {}
        accounts.extend(data.get("accounts") or [])
        cursor = data.get("cursor")
        if not data.get("has_next") or not cursor:
            break
    return accounts, None


def _get_fills_page_with_retry(provider: CoinbaseProvider, cursor: str | None):
    delay = _RETRY_BACKOFF_SECONDS
    result = None
    for _ in range(_MAX_PAGE_RETRIES):
        result = provider.get_fills(cursor=cursor)
        if result.status == "ok":
            return result
        time.sleep(delay)
        delay *= 2
    return None


def _fetch_all_fills(provider: CoinbaseProvider) -> tuple[list[dict], str | None]:
    """Cursor-pages through /orders/historical/fills unconditionally until `has_next` is
    false. If a page ultimately fails even after retries, pagination stops there but
    everything fetched so far is kept and processed rather than discarded."""
    fills: list[dict] = []
    cursor: str | None = None
    while True:
        result = _get_fills_page_with_retry(provider, cursor)
        if result is None:
            return fills, (
                "Coinbase hat die Anfrage zwischenzeitlich blockiert (Rate-Limit) — bereits gefundene "
                "Transaktionen wurden trotzdem verarbeitet. Bitte später erneut synchronisieren, um "
                "ältere Daten zu ergänzen."
            )

        data = result.data or {}
        fills.extend(data.get("fills") or [])
        cursor = data.get("cursor")
        if not data.get("has_next") or not cursor:
            break
        time.sleep(_PAGE_DELAY_SECONDS)

    return fills, None


def _record_all_transactions(db: Session, user_id: int, fills: list[dict], usd_eur_rate: Decimal) -> None:
    for fill in fills:
        try:
            parsed = _parse_product(fill["product_id"])
            if parsed is None:
                continue
            symbol, quote = parsed
            if quote not in _SUPPORTED_QUOTES:
                continue  # unsupported quote currency (e.g. GBP) -- skip rather than guess

            price_eur = _quote_to_eur(Decimal(str(fill["price"])), quote, usd_eur_rate)
            size = Decimal(str(fill["size"]))
            side = fill["side"].upper()
            trade_id = fill.get("trade_id") or fill["entry_id"]

            commission = fill.get("commission")
            fee_eur = _quote_to_eur(Decimal(str(commission)), quote, usd_eur_rate) if commission is not None else None

            upsert_transaction(
                db,
                user_id,
                source=_SOURCE,
                external_id=f"fill:{trade_id}",
                type_=TransactionType.buy if side == "BUY" else TransactionType.sell,
                asset=symbol,
                amount=size,
                price=price_eur,
                fee=fee_eur,
                currency="EUR",
                occurred_at=_parse_trade_datetime(fill["trade_time"]),
                raw=fill,
            )
        except (KeyError, ValueError, TypeError, InvalidOperation):
            continue  # malformed/unexpected row shape — skip rather than crash the whole sync

    db.commit()


def sync(db: Session, user_id: int) -> ExchangeSyncResult:
    provider = CoinbaseProvider()
    if not provider.is_configured:
        return ExchangeSyncResult(configured=False, error="Coinbase-API nicht konfiguriert.")

    accounts, account_error = _fetch_all_accounts(provider)
    if account_error and not accounts:
        return ExchangeSyncResult(configured=True, error=account_error)

    usd_eur_rate = _get_usd_eur_rate(db)
    if usd_eur_rate is None:
        return ExchangeSyncResult(
            configured=True,
            error="USD/EUR-Wechselkurs (für USD-quotierte Trades) ist gerade nicht verfügbar — bitte später erneut versuchen.",
        )

    fills, fetch_warning = _fetch_all_fills(provider)
    _record_all_transactions(db, user_id, fills, usd_eur_rate)

    balance_by_symbol: dict[str, Decimal] = {}
    for account in accounts:
        currency = account.get("currency")
        if not currency or currency in _SUPPORTED_QUOTES:
            continue  # EUR/USD cash balances aren't a tracked crypto position
        balance_by_symbol[currency] = balance_by_symbol.get(currency, Decimal(0)) + _account_quantity(account)
    symbols = [symbol for symbol, quantity in balance_by_symbol.items() if quantity > 0]

    results: list[AssetSyncResult] = []
    for symbol in symbols:
        holding = compute_holding(db, user_id, symbol, _SOURCE)
        actual_quantity = balance_by_symbol[symbol]
        mismatch_note = None
        # See module docstring: the replayed ledger can undercount/overcount a real position
        # when its origin predates the fills history — the real balance is authoritative for
        # quantity in that case, but the cost basis is no longer trustworthy.
        tolerance = max(Decimal("0.00000001"), actual_quantity * _QUANTITY_MISMATCH_RELATIVE_TOLERANCE)
        if abs(holding.quantity - actual_quantity) > tolerance:
            holding = AssetHolding(
                symbol=symbol, quantity=actual_quantity, average_cost_basis=None, cost_basis_incomplete=True
            )
            mismatch_note = (
                "Menge aus dem tatsächlichen Coinbase-Guthaben übernommen — die aufgezeichnete "
                "Transaktionshistorie war unvollständig, daher kein verlässlicher Anschaffungspreis verfügbar."
            )

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

        # CoinGecko's free tier enforces a short burst limit (see bitget_sync_service) -- a
        # small pause between coins keeps a multi-holding sync under it.
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
                note=mismatch_note,
                error=error,
            )
        )

    recompute_net_worth_snapshot(db, user_id)
    return ExchangeSyncResult(configured=True, assets=results, error=fetch_warning)
