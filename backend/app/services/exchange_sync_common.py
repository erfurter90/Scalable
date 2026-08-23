"""Exchange-agnostic pieces shared by every `{exchange}_sync_service.py` module. The ledger
replay math, the CoinGecko symbol mapping, transaction upserting, and the "replace only the
entries this exchange owns" logic don't care which exchange the data came from — only the
`source` value the caller tags rows with. Only the fetching (provider-specific auth, response
shapes, market/symbol conventions) differs per exchange and stays in each exchange's own
`{exchange}_sync_service.py` and `{exchange}_provider.py`.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.financial_snapshot import AssetSubcategory, EntryType, FinancialEntry
from app.models.transaction import Transaction, TransactionType
from app.services.financial_service import compute_value_from_quantity

# Maps a base-asset symbol (as reported by any exchange's balance/trade endpoints) to its
# CoinGecko coin id, so a synced holding reuses the existing quantity-tracked entry machinery
# (live price refresh, crypto breakdown chart, gain/loss display) exactly like a manually
# created one. Deliberately small and explicit: an unmapped symbol still gets its transactions
# recorded and quantity/cost-basis computed, it just isn't written as a FinancialEntry (nothing
# to price it with) — surfaced as a note.
SYMBOL_TO_COINGECKO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "SUI": "sui",
    "HBAR": "hedera-hashgraph",
    "KASPA": "kaspa",
    "KAS": "kaspa",  # Bitget's ticker for Kaspa (Bitvavo/others may use "KASPA")
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
    # "toncoin" is NOT a valid CoinGecko id (silently resolves to nothing) -- confirmed by
    # batch-checking every id in this table against the live API. The real id is
    # "the-open-network", also used for Bitget's "GRAM" listing: TON was originally launched
    # under the name "Gram" before Telegram's SEC settlement forced a rebrand, and some
    # exchanges still list the pre-rebrand ticker for the same coin (confirmed against a real
    # Bitget account: the app itself labels it "GRAM (prev. Toncoin)").
    "TON": "the-open-network",
    "GRAM": "the-open-network",
    "FARTCOIN": "fartcoin",
    "PUMP": "pump-fun",
    "SOMI": "somnia",
    "PORTAL": "portal-2",
    "POLYX": "polymesh",
    "XAI": "xai-blockchain",  # ambiguous ticker (shared with "sideshift-token") -- picked as
    # the far more likely match given Bitget's known listing history with Xai Games
    "JUP": "jupiter-exchange-solana",
    "POL": "polygon-ecosystem-token",  # Polygon's 2024 MATIC->POL token migration; distinct
    # CoinGecko id from "MATIC"/"matic-network" above
    "VET": "vechain",
    "VARA": "vara-network",
    "ACH": "alchemy-pay",
    "RNDR": "render-token",
    "FET": "fetch-ai",
    "AMP": "amp-token",
    "SKL": "skale",
    "FORTH": "ampleforth-governance-token",
    "NU": "nucypher",
    "GRT": "the-graph",
    "USDC": "usd-coin",
    "NMR": "numeraire",
    "ALGO": "algorand",
    "COMP": "compound-governance-token",
    "CGLD": "celo",  # Coinbase's legacy ticker for Celo's native token
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
class ExchangeSyncResult:
    configured: bool
    assets: list[AssetSyncResult] = field(default_factory=list)
    error: str | None = None


def upsert_transaction(
    db: Session,
    user_id: int,
    *,
    source: str,
    external_id: str,
    type_: TransactionType,
    asset: str,
    amount: Decimal,
    price: Decimal | None,
    fee: Decimal | None,
    currency: str,
    occurred_at: datetime,
    raw: dict,
) -> None:
    """Idempotent insert keyed by (user_id, source, external_id) — trades/deposits are
    immutable once settled on an exchange, so an existing row's own fields are left untouched.
    The one exception is `occurred_at`: rows synced before that column existed have it as
    None, so a later sync backfills it for free instead of requiring a one-off migration
    script to re-derive it from raw_row_json."""
    existing = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.source == source, Transaction.external_id == external_id)
        .first()
    )
    if existing is not None:
        if existing.occurred_at is None:
            existing.occurred_at = occurred_at
        return
    db.add(
        Transaction(
            user_id=user_id,
            date=occurred_at.date(),
            occurred_at=occurred_at,
            type=type_,
            asset=asset,
            amount=amount,
            price=price,
            fee=fee,
            currency=currency,
            source=source,
            external_id=external_id,
            raw_row_json=raw,
        )
    )


def compute_holding(db: Session, user_id: int, symbol: str, source: str) -> AssetHolding:
    """Pure replay of every stored Transaction for this asset from this exchange, oldest
    first — weighted-average cost basis, the same arithmetic as
    financial_service.add_purchase applied transaction-by-transaction instead of as a single
    blend."""
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.source == source, Transaction.asset == symbol)
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
            # Arrived from outside this exchange — no known purchase price. Quantity still
            # counts, but this batch contributes 0 to cost_total (never fabricate a price for
            # it), so any cost-basis number from here on would understate the true cost —
            # hence `incomplete` suppresses average_cost_basis to None in the final result
            # rather than presenting a partially-made-up figure as fact.
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


def replace_and_create_entry(
    db: Session,
    user_id: int,
    *,
    source: str,
    label: str,
    symbol: str,
    holding: AssetHolding,
    coingecko_id: str,
) -> tuple[list[str], Decimal | None, str | None]:
    """Deletes existing entries that are unambiguously "this exchange's holding" for this
    coin — either a previous sync's own row (source match), or a pre-existing manual entry
    the user already labeled with this exchange's name (e.g. "Bitget SUI") — then creates a
    fresh quantity-tracked entry from `holding` if there's anything left to hold. Matching on
    price_asset_id alone would also catch entries for the *same coin held elsewhere* (Trade
    Republic, Scalable, Coinbase, ...), silently deleting holdings that have nothing to do
    with this exchange. Returns (replaced_labels, current_value_eur, error).

    The live price is fetched *before* anything is deleted: a transient price-fetch failure
    (confirmed during development — CoinGecko's free tier rate-limited mid-sync) must leave
    the existing entry exactly as it was, not delete it and then fail to recreate it, which
    would make the position vanish from the app until the next successful sync."""
    existing_entries = (
        db.query(FinancialEntry)
        .filter(
            FinancialEntry.user_id == user_id,
            FinancialEntry.price_asset_id == coingecko_id,
            or_(FinancialEntry.source == source, FinancialEntry.label.ilike(f"%{label}%")),
        )
        .all()
    )
    replaced_labels = [entry.label for entry in existing_entries]

    if holding.quantity <= 0:
        for entry in existing_entries:
            db.delete(entry)
        db.commit()
        return replaced_labels, None, None

    try:
        current_value_eur = compute_value_from_quantity(holding.quantity, coingecko_id, "EUR")
    except ValueError as exc:
        return [], None, f"Aktueller Kurs für {symbol} konnte nicht abgerufen werden: {exc}"

    for entry in existing_entries:
        db.delete(entry)
    db.commit()

    subcategory = AssetSubcategory.btc.value if symbol == "BTC" else AssetSubcategory.crypto.value
    db.add(
        FinancialEntry(
            user_id=user_id,
            entry_type=EntryType.asset,
            category="holding",
            subcategory=subcategory,
            # No coin suffix in the label -- the frontend shows the coin in its own "Coin"
            # column, derived from price_asset_id, so the exchange name alone is enough.
            label=label,
            amount=current_value_eur,
            quantity=holding.quantity,
            price_asset_id=coingecko_id,
            average_cost_basis=holding.average_cost_basis,
            currency="EUR",
            snapshot_date=date.today(),
            source=source,
        )
    )
    db.commit()
    return replaced_labels, current_value_eur, None
