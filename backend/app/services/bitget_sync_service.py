"""Pulls the user's full Bitget transaction history and replays it into deterministic
per-asset holdings via the shared exchange_sync_common machinery — see that module for the
exchange-agnostic replay math, symbol mapping, and entry-replacement logic.

Bitget-specific and confirmed against a real account during development (not guessed from
docs alone, since bitget.com's own API docs are a JS single-page app that couldn't be
fetched directly):

- `/api/v2/spot/trade/fills` (the "obvious" trades endpoint) only returns roughly the last
  90 days — querying further back returns HTTP 400 ("time range illegal"), so it's useless
  for a Sparplan-style position built up over a year+. The full history instead lives in
  `/api/v2/tax/spot-record` (Bitget's tax-reporting ledger), which reaches back through the
  account's entire lifetime but caps each request to a 30-day window — hence the backward
  pagination in `_fetch_all_spot_records`.
- Each trade appears as **two** linked rows sharing a `bizOrderId`: one leg with
  `spotTaxType="Buy"` (the coin received) and one with `"Sell"` (the coin given up) — this is
  symmetric, e.g. selling BTC for USDT shows up as a BTC "Sell" leg + a USDT "Buy" leg, not
  fixed to "crypto is always the base". `amount` on each leg is already net of any fee (the
  fee is deducted from the coin received before it's added to the running `balance`), so fees
  are never added a second time here.
- `spotTaxType` also includes `"Deposit"` (external crypto arriving with no known purchase
  price — feeds `cost_basis_incomplete`, same as Bitvavo's deposit handling) and
  `"Transfer in"`/`"Transfer out"` (confirmed to be *internal* moves between the account's own
  wallets — e.g. funding → spot before a purchase — which the tax ledger design deliberately
  excludes from taxable events). Transfers are intentionally skipped rather than treated as
  external deposits/withdrawals: doing otherwise would falsely mark ordinary trades as
  cost-basis-incomplete every time funds were shuffled internally before a buy.
"""

import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.market_data import DataPointStatus
from app.models.transaction import TransactionType
from app.providers.bitget_provider import BitgetProvider, BitgetResult
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

_SOURCE = "bitget"
_LABEL = "Bitget"
_QUOTE_SYMBOL = "USDT"
_QUOTE_LIKE_COINS = {"USDT", "USDC", "EUR", "USD"}
# How far the replayed quantity may drift (relatively) from Bitget's own reported balance
# before it's treated as "the history is incomplete" rather than rounding noise. Relative,
# not absolute, since coin scales vary wildly (a fraction of a BTC vs. millions of a memecoin).
_QUANTITY_MISMATCH_RELATIVE_TOLERANCE = Decimal("0.005")

_DAY_MS = 24 * 60 * 60 * 1000
_MAX_WINDOW_MS = 29 * _DAY_MS  # Bitget rejects windows > 30 days
_LOOKBACK_MS = 5 * 365 * _DAY_MS  # always paged through in full -- see note below on why
_PAGE_DELAY_SECONDS = 0.5  # pacing between pages -- 0.15s still triggered 429s during development
_MAX_PAGE_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 1.5
_PRICE_LOOKUP_DELAY_SECONDS = 0.5  # pacing between per-coin CoinGecko price lookups


def _ms_to_datetime(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def _get_usd_eur_rate(db: Session) -> Decimal | None:
    """Fetched once per sync: USDT/USDC are USD-pegged 1:1, so this same rate covers every
    quote-currency conversion. Returns None if unavailable right now."""
    rate_point = market_data_service.get_fresh(db, "fx_usd_eur")
    if rate_point.status != DataPointStatus.ok or rate_point.value is None:
        return None
    return Decimal(str(rate_point.value))


def _quote_amount_to_eur(quote_coin: str, amount: Decimal, usd_eur_rate: Decimal) -> Decimal:
    if quote_coin == "EUR":
        return amount
    return (amount * usd_eur_rate).quantize(Decimal("0.01"))


def _get_page_with_retry(provider: BitgetProvider, start_ms: int, end_ms: int) -> BitgetResult | None:
    """A single page failure (observed during development: Bitget 429s if pages are requested
    too quickly) is usually transient — retried with backoff before giving up on it."""
    delay = _RETRY_BACKOFF_SECONDS
    result = None
    for _ in range(_MAX_PAGE_RETRIES):
        result = provider.get_tax_spot_records(start_ms, end_ms)
        if result.status == "ok":
            return result
        time.sleep(delay)
        delay *= 2
    return None


def _fetch_all_spot_records(provider: BitgetProvider) -> tuple[list[dict], str | None]:
    """Pages backward through /api/v2/tax/spot-record in <=29-day windows, unconditionally,
    all the way to `_LOOKBACK_MS`.

    An earlier version stopped after a run of consecutive empty pages as a cheap stand-in for
    "reached account creation" — this was WRONG and confirmed to silently drop real history
    during development: a real account had a year-long lull between two trading periods (well
    past any reasonable "stop early" threshold), and stopping there meant the large buy that
    actually built up the position was never seen, making the replay show far more sold than
    ever bought for that coin. Gaps in trading activity are normal and must never be read as
    "no more history exists" -- there is no substitute for walking the whole window.

    If a page ultimately fails even after retries, pagination stops there but everything
    fetched so far is kept and processed rather than discarded — a rate limit hit deep in a
    multi-year history shouldn't throw away the months of trades already retrieved before it."""
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    oldest_allowed = now_ms - _LOOKBACK_MS
    end = now_ms
    records: list[dict] = []

    while end > oldest_allowed:
        start = max(end - _MAX_WINDOW_MS, oldest_allowed)
        result = _get_page_with_retry(provider, start, end)
        if result is None:
            return records, (
                "Bitget hat die Anfrage zwischenzeitlich blockiert (Rate-Limit) — bereits gefundene "
                "Transaktionen wurden trotzdem verarbeitet. Bitte später erneut synchronisieren, um "
                "ältere Daten zu ergänzen."
            )

        records.extend(result.data or [])
        end = start
        time.sleep(_PAGE_DELAY_SECONDS)

    return records, None


def _process_trade_pair(db: Session, user_id: int, biz_order_id: str, legs: list[dict], usd_eur_rate: Decimal) -> None:
    buy_leg = next((leg for leg in legs if leg.get("spotTaxType") == "Buy"), None)
    sell_leg = next((leg for leg in legs if leg.get("spotTaxType") == "Sell"), None)
    if buy_leg is None or sell_leg is None:
        return  # not a simple one-buy-one-sell pair — skip rather than guess

    try:
        buy_coin = buy_leg["coin"]
        sell_coin = sell_leg["coin"]
        buy_amount = Decimal(str(buy_leg["amount"]))  # already net of fee
        sell_amount = abs(Decimal(str(sell_leg["amount"])))
        occurred_at = _ms_to_datetime(int(buy_leg["ts"]))

        buy_is_quote = buy_coin in _QUOTE_LIKE_COINS
        sell_is_quote = sell_coin in _QUOTE_LIKE_COINS

        if sell_is_quote and not buy_is_quote:
            # Bought a tracked coin, paid with a quote currency.
            if buy_amount == 0:
                return
            price_eur = _quote_amount_to_eur(sell_coin, sell_amount / buy_amount, usd_eur_rate)
            upsert_transaction(
                db, user_id, source=_SOURCE, external_id=f"trade:{biz_order_id}", type_=TransactionType.buy,
                asset=buy_coin, amount=buy_amount, price=price_eur, fee=None, currency="EUR",
                occurred_at=occurred_at, raw={"legs": legs},
            )
        elif buy_is_quote and not sell_is_quote:
            # Sold a tracked coin, received a quote currency.
            if sell_amount == 0:
                return
            proceeds_eur = _quote_amount_to_eur(buy_coin, buy_amount, usd_eur_rate)
            price_eur = (proceeds_eur / sell_amount).quantize(Decimal("0.01"))
            upsert_transaction(
                db, user_id, source=_SOURCE, external_id=f"trade:{biz_order_id}", type_=TransactionType.sell,
                asset=sell_coin, amount=sell_amount, price=price_eur, fee=None, currency="EUR",
                occurred_at=occurred_at, raw={"legs": legs},
            )
        # else: quote-to-quote (e.g. USDT->EUR) or a direct altcoin-to-altcoin swap — neither
        # is a plain "buy/sell a tracked coin against a known-EUR-value currency" case; skipped
        # rather than guessed.
    except (KeyError, ValueError, TypeError, InvalidOperation, ZeroDivisionError):
        return


def _process_single_record(db: Session, user_id: int, row: dict) -> None:
    tax_type = row.get("spotTaxType") or ""
    if "Deposit" in tax_type:
        type_ = TransactionType.deposit
    elif "Withdraw" in tax_type:
        type_ = TransactionType.withdrawal
    else:
        return  # "Transfer in/out" (internal), "fiat_recharge_in", or unrecognized — skip

    try:
        upsert_transaction(
            db, user_id, source=_SOURCE, external_id=f"single:{row['id']}", type_=type_,
            asset=row["coin"], amount=abs(Decimal(str(row["amount"]))), price=None, fee=None,
            currency="EUR", occurred_at=_ms_to_datetime(int(row["ts"])), raw=row,
        )
    except (KeyError, ValueError, TypeError):
        return


def _record_all_transactions(db: Session, user_id: int, records: list[dict], usd_eur_rate: Decimal) -> None:
    by_biz_order: dict[str, list[dict]] = {}
    for row in records:
        biz_order_id = row.get("bizOrderId")
        if not biz_order_id:
            continue
        by_biz_order.setdefault(biz_order_id, []).append(row)

    for biz_order_id, legs in by_biz_order.items():
        if len(legs) == 2 and legs[0].get("coin") != legs[1].get("coin"):
            _process_trade_pair(db, user_id, biz_order_id, legs, usd_eur_rate)
        else:
            for row in legs:
                _process_single_record(db, user_id, row)

    db.commit()


def sync(db: Session, user_id: int) -> ExchangeSyncResult:
    provider = BitgetProvider()
    if not provider.is_configured:
        return ExchangeSyncResult(configured=False, error="Bitget-API nicht konfiguriert.")

    balance_result = provider.get_balance()
    if balance_result.status != "ok":
        return ExchangeSyncResult(
            configured=True, error=f"Guthaben konnte nicht geladen werden: {balance_result.error_message}"
        )

    usd_eur_rate = _get_usd_eur_rate(db)
    if usd_eur_rate is None:
        return ExchangeSyncResult(
            configured=True,
            error="USD/EUR-Wechselkurs (für die USDT-Umrechnung) ist gerade nicht verfügbar — bitte später erneut versuchen.",
        )

    # A partial-history warning (rate limit hit mid-pagination) doesn't abort the sync -- keep
    # and process whatever was fetched, and surface the warning alongside the results below.
    records, fetch_warning = _fetch_all_spot_records(provider)
    _record_all_transactions(db, user_id, records, usd_eur_rate)

    balance_by_symbol: dict[str, Decimal] = {
        row["coin"]: (
            Decimal(str(row.get("available", 0))) + Decimal(str(row.get("frozen", 0))) + Decimal(str(row.get("locked", 0)))
        )
        for row in (balance_result.data or [])
        if row.get("coin") not in _QUOTE_LIKE_COINS
    }
    symbols = [symbol for symbol, quantity in balance_by_symbol.items() if quantity > 0]

    results: list[AssetSyncResult] = []
    for symbol in symbols:
        holding = compute_holding(db, user_id, symbol, _SOURCE)
        actual_quantity = balance_by_symbol[symbol]
        mismatch_note = None
        # The replayed ledger can undercount or overcount a real position when its history
        # predates what Bitget's tax-record API exposes -- confirmed during development on a
        # real account where ~527 units of a coin had no discoverable acquisition record at
        # all, even scanning back years. When the two disagree beyond rounding noise, the
        # exchange's own reported balance is authoritative for *quantity* -- but the cost
        # basis computed from an incomplete history is not trustworthy, so it's dropped rather
        # than shown as if it were exact.
        tolerance = max(Decimal("0.00000001"), actual_quantity * _QUANTITY_MISMATCH_RELATIVE_TOLERANCE)
        if abs(holding.quantity - actual_quantity) > tolerance:
            holding = AssetHolding(
                symbol=symbol, quantity=actual_quantity, average_cost_basis=None, cost_basis_incomplete=True
            )
            mismatch_note = (
                "Menge aus dem tatsächlichen Bitget-Guthaben übernommen — die aufgezeichnete "
                "Transaktionshistorie war unvollständig (z. B. sehr alte Bestände ohne auffindbaren "
                "Beleg), daher kein verlässlicher Anschaffungspreis verfügbar."
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

        # CoinGecko's free tier enforces a short burst limit (confirmed during development:
        # the first ~5 rapid price lookups in this loop succeeded, everything after failed
        # with 429) -- a small pause between coins keeps a multi-holding sync under it.
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
