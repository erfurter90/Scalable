"""Pulls the user's full Bitvavo transaction history and replays it into deterministic
per-asset holdings (quantity + weighted-average EUR cost basis) — same arithmetic as
financial_service.add_purchase, just applied to a whole ledger instead of a single blend.

Writes a Transaction audit row per trade/deposit/withdrawal (idempotent via the
(user_id, source, external_id) unique constraint — re-running a sync after a new Sparplan
purchase only adds the new rows) and then replaces the corresponding FinancialEntry rows so
the rest of the app (dashboard, allocation charts, gain/loss display) sees the result as an
ordinary quantity-tracked holding — no special-casing needed anywhere else.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.financial_snapshot import AssetSubcategory, EntryType, FinancialEntry
from app.models.transaction import Transaction, TransactionType
from app.providers.bitvavo_provider import BitvavoProvider
from app.services.financial_service import compute_value_from_quantity, recompute_net_worth_snapshot

# Bitvavo trades are only ever fetched for X-EUR markets here, so price/fee are always EUR
# already — no FX conversion step needed (unlike the manual purchase-price entry flow, which
# also accepts USD).
_QUOTE_CURRENCY = "EUR"

# Maps a Bitvavo base-asset symbol to its CoinGecko coin id, so a synced holding reuses the
# existing quantity-tracked entry machinery (live price refresh, crypto breakdown chart,
# gain/loss display) exactly like a manually created one. Deliberately small and explicit: an
# unmapped symbol still gets its transactions recorded and quantity/cost-basis computed, it
# just isn't written as a FinancialEntry (nothing to price it with) — surfaced as a note.
SYMBOL_TO_COINGECKO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "SUI": "sui",
    "HBAR": "hedera-hashgraph",
    "KASPA": "kaspa",
    "ONDO": "ondo-finance",
    "ADA": "cardano",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "LTC": "litecoin",
    "LINK": "chainlink",
    "BNB": "binancecoin",
    "TRX": "tron",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "XLM": "stellar",
    "ATOM": "cosmos",
    "XMR": "monero",
    "UNI": "uniswap",
    "NEAR": "near",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "SHIB": "shiba-inu",
    "PEPE": "pepe",
    "TON": "toncoin",
}


@dataclass
class AssetHolding:
    symbol: str
    quantity: Decimal
    average_cost_basis: Decimal | None
    cost_basis_incomplete: bool


@dataclass
class AssetSyncResult:
    symbol: str
    coingecko_id: str | None
    quantity: Decimal
    average_cost_basis: Decimal | None
    cost_basis_incomplete: bool
    current_value_eur: Decimal | None
    replaced_entry_labels: list[str] = field(default_factory=list)
    note: str | None = None
    error: str | None = None


@dataclass
class BitvavoSyncResult:
    configured: bool
    assets: list[AssetSyncResult] = field(default_factory=list)
    error: str | None = None


def _ms_to_date(timestamp_ms: int) -> date:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date()


def _upsert_transaction(
    db: Session,
    user_id: int,
    *,
    external_id: str,
    type_: TransactionType,
    asset: str,
    amount: Decimal,
    price: Decimal | None,
    fee: Decimal | None,
    txn_date: date,
    raw: dict,
) -> None:
    existing = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id, Transaction.source == "bitvavo", Transaction.external_id == external_id
        )
        .first()
    )
    if existing is not None:
        return  # trades/deposits are immutable once settled on Bitvavo — nothing to update
    db.add(
        Transaction(
            user_id=user_id,
            date=txn_date,
            type=type_,
            asset=asset,
            amount=amount,
            price=price,
            fee=fee,
            currency=_QUOTE_CURRENCY,
            source="bitvavo",
            external_id=external_id,
            raw_row_json=raw,
        )
    )


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
            _upsert_transaction(
                db,
                user_id,
                external_id=str(trade["id"]),
                type_=TransactionType.buy if trade["side"] == "buy" else TransactionType.sell,
                asset=symbol,
                amount=Decimal(str(trade["amount"])),
                price=Decimal(str(trade["price"])),
                fee=Decimal(str(fee)) if fee is not None else None,
                txn_date=_ms_to_date(int(trade["timestamp"])),
                raw=trade,
            )
        except (KeyError, ValueError, TypeError):
            continue  # malformed row from the API — skip rather than crash the whole sync

    deposits_result = provider.get_deposit_history(symbol)
    for deposit in (deposits_result.data or []) if deposits_result.status == "ok" else []:
        try:
            external_id = f"deposit:{deposit.get('txId') or deposit.get('paymentId') or deposit['timestamp']}"
            _upsert_transaction(
                db,
                user_id,
                external_id=external_id,
                type_=TransactionType.deposit,
                asset=symbol,
                amount=Decimal(str(deposit["amount"])),
                price=None,
                fee=Decimal(str(deposit["fee"])) if deposit.get("fee") is not None else None,
                txn_date=_ms_to_date(int(deposit["timestamp"])),
                raw=deposit,
            )
        except (KeyError, ValueError, TypeError):
            continue

    withdrawals_result = provider.get_withdrawal_history(symbol)
    for withdrawal in (withdrawals_result.data or []) if withdrawals_result.status == "ok" else []:
        try:
            external_id = f"withdrawal:{withdrawal.get('txId') or withdrawal.get('paymentId') or withdrawal['timestamp']}"
            _upsert_transaction(
                db,
                user_id,
                external_id=external_id,
                type_=TransactionType.withdrawal,
                asset=symbol,
                amount=Decimal(str(withdrawal["amount"])),
                price=None,
                fee=Decimal(str(withdrawal["fee"])) if withdrawal.get("fee") is not None else None,
                txn_date=_ms_to_date(int(withdrawal["timestamp"])),
                raw=withdrawal,
            )
        except (KeyError, ValueError, TypeError):
            continue

    db.commit()
    return None


def compute_holding(db: Session, user_id: int, symbol: str) -> AssetHolding:
    """Pure replay of every stored bitvavo Transaction for this asset, oldest first — weighted-
    average cost basis, the same arithmetic as financial_service.add_purchase applied
    transaction-by-transaction instead of as a single blend."""
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.source == "bitvavo", Transaction.asset == symbol)
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    quantity = Decimal(0)
    cost_total = Decimal(0)
    incomplete = False

    for txn in transactions:
        amount = Decimal(str(txn.amount))
        if txn.type == TransactionType.buy:
            price = Decimal(str(txn.price)) if txn.price is not None else Decimal(0)
            fee = Decimal(str(txn.fee)) if txn.fee is not None else Decimal(0)
            cost_total += amount * price + fee
            quantity += amount
        elif txn.type == TransactionType.deposit:
            # Arrived from outside Bitvavo — no known purchase price. Quantity still counts,
            # but this batch contributes 0 to cost_total (never fabricate a price for it), so
            # any cost-basis number from here on would understate the true cost — hence
            # `incomplete` suppresses average_cost_basis to None in the final result rather
            # than presenting a partially-made-up figure as fact.
            quantity += amount
            incomplete = True
        elif txn.type in (TransactionType.sell, TransactionType.withdrawal):
            if quantity > 0:
                fraction_remaining = max(Decimal(0), (quantity - amount) / quantity)
                cost_total *= fraction_remaining
            quantity = max(Decimal(0), quantity - amount)

    if quantity <= 0:
        return AssetHolding(
            symbol=symbol, quantity=Decimal(0), average_cost_basis=None, cost_basis_incomplete=incomplete
        )

    average_cost_basis = None if incomplete else (cost_total / quantity).quantize(Decimal("0.01"))
    return AssetHolding(
        symbol=symbol, quantity=quantity, average_cost_basis=average_cost_basis, cost_basis_incomplete=incomplete
    )


def sync(db: Session, user_id: int) -> BitvavoSyncResult:
    provider = BitvavoProvider()
    if not provider.is_configured:
        return BitvavoSyncResult(configured=False, error="Bitvavo-API nicht konfiguriert.")

    balance_result = provider.get_balance()
    if balance_result.status != "ok":
        return BitvavoSyncResult(
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

        holding = compute_holding(db, user_id, symbol)
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

        # Only replace entries that are already, unambiguously "the Bitvavo holding" for this
        # coin -- either a previous sync's own row, or a pre-existing manual entry the user
        # already labeled as their Bitvavo position (e.g. "Bitvavo Wallet"). Matching on
        # price_asset_id alone would also catch entries for the *same coin held elsewhere*
        # (Trade Republic, Scalable, Coinbase, ...), silently deleting holdings that have
        # nothing to do with Bitvavo.
        existing_entries = (
            db.query(FinancialEntry)
            .filter(
                FinancialEntry.user_id == user_id,
                FinancialEntry.price_asset_id == coingecko_id,
                or_(FinancialEntry.source == "bitvavo", FinancialEntry.label.ilike("%bitvavo%")),
            )
            .all()
        )
        replaced_labels = [entry.label for entry in existing_entries]
        for entry in existing_entries:
            db.delete(entry)
        db.commit()

        current_value_eur = None
        if holding.quantity > 0:
            try:
                current_value_eur = compute_value_from_quantity(holding.quantity, coingecko_id, "EUR")
                subcategory = AssetSubcategory.btc.value if symbol == "BTC" else AssetSubcategory.crypto.value
                db.add(
                    FinancialEntry(
                        user_id=user_id,
                        entry_type=EntryType.asset,
                        category="holding",
                        subcategory=subcategory,
                        label=f"Bitvavo {symbol}",
                        amount=current_value_eur,
                        quantity=holding.quantity,
                        price_asset_id=coingecko_id,
                        average_cost_basis=holding.average_cost_basis,
                        currency="EUR",
                        snapshot_date=date.today(),
                        source="bitvavo",
                    )
                )
                db.commit()
            except ValueError as exc:
                results.append(
                    AssetSyncResult(
                        symbol=symbol,
                        coingecko_id=coingecko_id,
                        quantity=holding.quantity,
                        average_cost_basis=holding.average_cost_basis,
                        cost_basis_incomplete=holding.cost_basis_incomplete,
                        current_value_eur=None,
                        replaced_entry_labels=replaced_labels,
                        error=f"Aktueller Kurs für {symbol} konnte nicht abgerufen werden: {exc}",
                    )
                )
                continue

        results.append(
            AssetSyncResult(
                symbol=symbol,
                coingecko_id=coingecko_id,
                quantity=holding.quantity,
                average_cost_basis=holding.average_cost_basis,
                cost_basis_incomplete=holding.cost_basis_incomplete,
                current_value_eur=current_value_eur,
                replaced_entry_labels=replaced_labels,
            )
        )

    recompute_net_worth_snapshot(db, user_id)
    return BitvavoSyncResult(configured=True, assets=results)
