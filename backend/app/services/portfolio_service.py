"""Groups the user's current asset entries by subcategory (cash/btc/crypto/stocks/etf/other)
into a percentage breakdown. Deterministic arithmetic only — no LLM involvement.

Uses ALL of the user's asset entries, not just ones sharing a particular snapshot_date: that
field is informational per entry (e.g. "when I bought this"), not a grouping key — see
financial_service.recompute_net_worth_snapshot for the full reasoning. Filtering by date here
would silently drop entries dated differently from the "most recent" one (e.g. a holding
whose date reflects its actual purchase date) out of the current totals.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.financial_snapshot import AssetSubcategory, EntryType, FinancialEntry
from app.schemas.portfolio import AllocationItem, CryptoAllocationItem, CryptoBreakdownOut, PortfolioAllocationOut


def get_allocation(db: Session, user_id: int) -> PortfolioAllocationOut | None:
    entries = (
        db.query(FinancialEntry)
        .filter(FinancialEntry.user_id == user_id, FinancialEntry.entry_type == EntryType.asset)
        .all()
    )
    if not entries:
        return None

    totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for entry in entries:
        totals[entry.subcategory] += Decimal(str(entry.amount))

    # `amount` can carry more than 2 decimal places (see FinancialEntry.amount), e.g. a
    # quantity-derived or manually entered crypto value — round display totals to cents so
    # the allocation view reads like money, consistent with NetWorthSnapshot elsewhere.
    total_assets = sum(totals.values(), Decimal(0)).quantize(Decimal("0.01"))

    breakdown = [
        AllocationItem(
            subcategory=subcategory,
            amount=amount.quantize(Decimal("0.01")),
            percent_of_total=float(amount / total_assets * 100) if total_assets else 0.0,
        )
        for subcategory, amount in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]

    btc_amount = totals.get(AssetSubcategory.btc.value, Decimal(0))
    investments_total = sum(
        (amount for subcategory, amount in totals.items() if subcategory != AssetSubcategory.cash.value),
        Decimal(0),
    )

    return PortfolioAllocationOut(
        snapshot_date=date.today(),
        total_assets=total_assets,
        breakdown=breakdown,
        btc_percent_of_assets=float(btc_amount / total_assets * 100) if total_assets else 0.0,
        btc_percent_of_investments=float(btc_amount / investments_total * 100) if investments_total else 0.0,
    )


def get_crypto_breakdown(db: Session, user_id: int) -> CryptoBreakdownOut | None:
    """Individual-coin breakdown of the "andere Krypto" bucket only — BTC already gets its
    own slice in the main allocation, so re-showing it here would be redundant."""
    entries = (
        db.query(FinancialEntry)
        .filter(
            FinancialEntry.user_id == user_id,
            FinancialEntry.entry_type == EntryType.asset,
            FinancialEntry.subcategory == AssetSubcategory.crypto.value,
        )
        .all()
    )
    if not entries:
        return None

    totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for entry in entries:
        # Group by coin id when known (merges e.g. two separate SOL holdings into one slice);
        # entries without one (a manually typed EUR amount, no live-price tracking) can't be
        # merged with anything, so each keeps its own label as the grouping key.
        key = entry.price_asset_id or entry.label
        totals[key] += Decimal(str(entry.amount))

    total_crypto = sum(totals.values(), Decimal(0)).quantize(Decimal("0.01"))

    breakdown = [
        CryptoAllocationItem(
            coin=coin,
            amount=amount.quantize(Decimal("0.01")),
            percent_of_crypto=float(amount / total_crypto * 100) if total_crypto else 0.0,
        )
        for coin, amount in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return CryptoBreakdownOut(snapshot_date=date.today(), total_crypto=total_crypto, breakdown=breakdown)
