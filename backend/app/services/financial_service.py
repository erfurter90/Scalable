"""Financial entry CRUD plus net-worth aggregation. All money math happens here in plain
Decimal arithmetic — deterministic, no LLM involvement, unit-tested directly."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.financial_snapshot import (
    AssetSubcategory,
    EntryType,
    FinancialEntry,
    NetWorthSnapshot,
)
from app.models.market_data import DataPointStatus
from app.providers.registry import get_price_provider
from app.schemas.financial import FinancialEntryCreate, FinancialEntryUpdate
from app.services import market_data_service

_INVESTMENT_SUBCATEGORIES = {
    AssetSubcategory.btc.value,
    AssetSubcategory.crypto.value,
    AssetSubcategory.stocks.value,
    AssetSubcategory.etf.value,
    AssetSubcategory.other.value,
}


def _validate_subcategory(entry_type: EntryType, subcategory: str | None) -> None:
    if entry_type == EntryType.asset and subcategory not in {s.value for s in AssetSubcategory}:
        raise ValueError(
            f"asset entries require a valid subcategory, one of: {[s.value for s in AssetSubcategory]}"
        )


def compute_value_from_quantity(quantity: Decimal, price_asset_id: str, currency: str) -> Decimal:
    """Fetches the current price for `price_asset_id` and returns quantity * price. Raises
    ValueError (never fabricates a number) if the price can't be reliably fetched right now —
    the caller surfaces this as a 400 so the user can retry or enter an amount manually."""
    result = get_price_provider().fetch_price(price_asset_id, currency.lower())
    if result.status != "ok" or result.value is None:
        reason = result.error_message or "price currently unavailable"
        raise ValueError(f"Could not fetch a current price for '{price_asset_id}' in {currency}: {reason}")
    return (quantity * result.value).quantize(Decimal("0.01"))


def _resolve_amount(
    amount: Decimal | None, quantity: Decimal | None, price_asset_id: str | None, currency: str
) -> Decimal:
    if amount is not None:
        return amount
    if quantity is None or not price_asset_id:
        raise ValueError("Either 'amount', or both 'quantity' and 'price_asset_id', must be provided.")
    return compute_value_from_quantity(quantity, price_asset_id, currency)


def _convert_purchase_price_to_eur(db: Session, price: Decimal, currency: str) -> Decimal:
    """Converts a purchase price entered in EUR or USD into EUR (the app's base currency for
    average cost basis tracking), using the current USD/EUR rate — never a fabricated or
    stale one. Raises ValueError if the currency isn't supported or the rate can't be fetched."""
    currency = currency.upper()
    if currency == "EUR":
        return price
    if currency != "USD":
        raise ValueError(f"Nur EUR oder USD werden als Anschaffungswährung unterstützt (erhalten: '{currency}').")

    rate_point = market_data_service.get_fresh(db, "fx_usd_eur")
    if rate_point.status != DataPointStatus.ok or rate_point.value is None:
        reason = rate_point.error_message or "Wechselkurs derzeit nicht verfügbar"
        raise ValueError(f"Aktueller USD/EUR-Wechselkurs konnte nicht abgerufen werden: {reason}")

    return (price * Decimal(str(rate_point.value))).quantize(Decimal("0.01"))


def list_entries(
    db: Session,
    user_id: int,
    entry_type: EntryType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[FinancialEntry]:
    query = db.query(FinancialEntry).filter(FinancialEntry.user_id == user_id)
    if entry_type is not None:
        query = query.filter(FinancialEntry.entry_type == entry_type)
    if date_from is not None:
        query = query.filter(FinancialEntry.snapshot_date >= date_from)
    if date_to is not None:
        query = query.filter(FinancialEntry.snapshot_date <= date_to)
    return query.order_by(FinancialEntry.snapshot_date.desc(), FinancialEntry.id.desc()).all()


def create_entry(db: Session, user_id: int, data: FinancialEntryCreate) -> FinancialEntry:
    _validate_subcategory(data.entry_type, data.subcategory)
    resolved_amount = _resolve_amount(data.amount, data.quantity, data.price_asset_id, data.currency)

    average_cost_basis = None
    if data.purchase_price is not None:
        purchase_currency = data.purchase_price_currency or "EUR"
        average_cost_basis = _convert_purchase_price_to_eur(db, data.purchase_price, purchase_currency)

    entry_fields = data.model_dump(exclude={"purchase_price", "purchase_price_currency"})
    entry = FinancialEntry(
        user_id=user_id, **{**entry_fields, "amount": resolved_amount, "average_cost_basis": average_cost_basis}
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    recompute_net_worth_snapshot(db, user_id)
    return entry


def add_purchase(
    db: Session,
    user_id: int,
    entry_id: int,
    additional_quantity: Decimal,
    purchase_price: Decimal,
    purchase_price_currency: str,
) -> FinancialEntry | None:
    """Records buying more of an existing quantity-tracked holding ("Nachkauf"): blends the
    new purchase into the running weighted-average cost basis, bumps total quantity, and
    refreshes the current EUR value at the live price. Returns None if the entry doesn't
    exist; raises ValueError if it isn't quantity-tracked or the price/FX rate can't be
    resolved right now."""
    entry = (
        db.query(FinancialEntry).filter(FinancialEntry.id == entry_id, FinancialEntry.user_id == user_id).first()
    )
    if entry is None:
        return None
    if entry.quantity is None or not entry.price_asset_id:
        raise ValueError("Nachkäufe sind nur für mengenbasierte Einträge (mit Menge + Coin) möglich.")

    if entry.average_cost_basis is None:
        raise ValueError(
            "Für diesen Eintrag ist noch kein Anschaffungspreis erfasst — bitte zuerst den "
            "Anschaffungspreis für die bestehende Menge festlegen, bevor ein Nachkauf blendet wird."
        )

    price_in_eur = _convert_purchase_price_to_eur(db, purchase_price, purchase_price_currency)

    old_quantity = Decimal(str(entry.quantity))
    old_avg = Decimal(str(entry.average_cost_basis))
    new_quantity = old_quantity + additional_quantity

    # Weighted-average cost basis: blend the existing average (over old_quantity) with the new
    # purchase (over additional_quantity).
    new_avg = ((old_avg * old_quantity) + (price_in_eur * additional_quantity)) / new_quantity

    entry.quantity = new_quantity
    entry.average_cost_basis = new_avg.quantize(Decimal("0.01"))
    entry.amount = compute_value_from_quantity(new_quantity, entry.price_asset_id, entry.currency)

    db.commit()
    db.refresh(entry)

    recompute_net_worth_snapshot(db, user_id)
    return entry


def set_cost_basis(
    db: Session, user_id: int, entry_id: int, purchase_price: Decimal, purchase_price_currency: str
) -> FinancialEntry | None:
    """Records what was paid, on average, for the entry's *current* quantity — for a holding
    that was quantity-tracked without ever recording a purchase price (e.g. imported or
    created before this feature). Replaces any existing average outright rather than blending
    — use add_purchase() instead once a cost basis is established, so new buys blend in
    correctly rather than overwriting the history. Quantity and current value are untouched."""
    entry = (
        db.query(FinancialEntry).filter(FinancialEntry.id == entry_id, FinancialEntry.user_id == user_id).first()
    )
    if entry is None:
        return None
    if entry.quantity is None or not entry.price_asset_id:
        raise ValueError("Ein Anschaffungspreis ist nur für mengenbasierte Einträge (mit Menge + Coin) möglich.")

    price_in_eur = _convert_purchase_price_to_eur(db, purchase_price, purchase_price_currency)
    entry.average_cost_basis = price_in_eur.quantize(Decimal("0.01"))

    db.commit()
    db.refresh(entry)
    return entry


def update_entry(db: Session, user_id: int, entry_id: int, data: FinancialEntryUpdate) -> FinancialEntry | None:
    entry = (
        db.query(FinancialEntry).filter(FinancialEntry.id == entry_id, FinancialEntry.user_id == user_id).first()
    )
    if entry is None:
        return None

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)
    _validate_subcategory(entry.entry_type, entry.subcategory)

    # If quantity/price_asset_id changed but this update didn't also give an explicit amount,
    # recompute the EUR value from the (possibly new) quantity/coin at the current price —
    # otherwise a quantity-only edit would silently leave the old, now-wrong amount in place.
    if ("quantity" in updates or "price_asset_id" in updates) and "amount" not in updates:
        entry.amount = _resolve_amount(None, entry.quantity, entry.price_asset_id, entry.currency)

    db.commit()
    db.refresh(entry)

    recompute_net_worth_snapshot(db, user_id)
    return entry


def refresh_entry_value(db: Session, user_id: int, entry_id: int) -> FinancialEntry | None:
    """Re-fetches the current price for a quantity-tracked entry and updates its stored EUR
    amount — the one-click fix for "the price moved since I last saved this" without having
    to re-enter the quantity. Returns None if the entry doesn't exist; raises ValueError if
    the entry isn't quantity-tracked or the price can't be fetched right now."""
    entry = (
        db.query(FinancialEntry).filter(FinancialEntry.id == entry_id, FinancialEntry.user_id == user_id).first()
    )
    if entry is None:
        return None
    if entry.quantity is None or not entry.price_asset_id:
        raise ValueError("This entry has no quantity/coin configured — nothing to refresh.")

    entry.amount = compute_value_from_quantity(Decimal(str(entry.quantity)), entry.price_asset_id, entry.currency)
    db.commit()
    db.refresh(entry)

    recompute_net_worth_snapshot(db, user_id)
    return entry


def delete_entry(db: Session, user_id: int, entry_id: int) -> bool:
    entry = (
        db.query(FinancialEntry).filter(FinancialEntry.id == entry_id, FinancialEntry.user_id == user_id).first()
    )
    if entry is None:
        return False

    db.delete(entry)
    db.commit()

    recompute_net_worth_snapshot(db, user_id)
    return True


def recompute_net_worth_snapshot(db: Session, user_id: int) -> NetWorthSnapshot:
    """Re-sums ALL of the user's current FinancialEntry rows and upserts *today's*
    NetWorthSnapshot row. Called after every create/update/delete so dashboard reads never
    need to re-aggregate raw entries themselves.

    Deliberately NOT filtered by each entry's own snapshot_date: that field is informational
    per entry (e.g. "when I bought this" or "when I last verified this balance"), not a
    grouping key — the app has exactly one row per holding (edits mutate it in place, they
    don't append a new dated row), so "current net worth" is simply the sum of everything the
    user currently has, regardless of which date is stamped on which entry. History instead
    comes from recording that total under today's date every time it's recomputed."""
    today = date.today()
    entries = db.query(FinancialEntry).filter(FinancialEntry.user_id == user_id).all()

    total_assets = Decimal(0)
    total_liabilities = Decimal(0)
    cash_total = Decimal(0)
    investments_total = Decimal(0)

    for entry in entries:
        amount = Decimal(str(entry.amount))
        if entry.entry_type == EntryType.asset:
            total_assets += amount
            if entry.subcategory == AssetSubcategory.cash.value:
                cash_total += amount
            elif entry.subcategory in _INVESTMENT_SUBCATEGORIES:
                investments_total += amount
        elif entry.entry_type == EntryType.liability:
            total_liabilities += amount
        # income/expense entries don't contribute to point-in-time net worth

    net_worth = total_assets - total_liabilities

    snapshot = (
        db.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.user_id == user_id, NetWorthSnapshot.snapshot_date == today)
        .first()
    )
    if snapshot is None:
        snapshot = NetWorthSnapshot(user_id=user_id, snapshot_date=today)
        db.add(snapshot)

    snapshot.total_assets = total_assets
    snapshot.total_liabilities = total_liabilities
    snapshot.net_worth = net_worth
    snapshot.cash_total = cash_total
    snapshot.investments_total = investments_total

    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_net_worth_history(
    db: Session, user_id: int, date_from: date | None = None, date_to: date | None = None
) -> list[NetWorthSnapshot]:
    query = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.user_id == user_id)
    if date_from is not None:
        query = query.filter(NetWorthSnapshot.snapshot_date >= date_from)
    if date_to is not None:
        query = query.filter(NetWorthSnapshot.snapshot_date <= date_to)
    return query.order_by(NetWorthSnapshot.snapshot_date.asc()).all()


def get_current_net_worth(db: Session, user_id: int) -> NetWorthSnapshot | None:
    return (
        db.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.user_id == user_id)
        .order_by(NetWorthSnapshot.snapshot_date.desc())
        .first()
    )


def get_net_worth_change(db: Session, user_id: int, days: int) -> dict | None:
    """Used by both the dashboard and the LLM handoff (see llm/functions.py) — computed once
    here so the chat assistant never has to guess a percentage change itself."""
    latest = get_current_net_worth(db, user_id)
    if latest is None:
        return None

    target_date = latest.snapshot_date - timedelta(days=days)
    past = (
        db.query(NetWorthSnapshot)
        .filter(NetWorthSnapshot.user_id == user_id, NetWorthSnapshot.snapshot_date <= target_date)
        .order_by(NetWorthSnapshot.snapshot_date.desc())
        .first()
    )
    if past is None:
        return None

    change_abs = latest.net_worth - past.net_worth
    change_pct = float(change_abs / past.net_worth * 100) if past.net_worth else None

    return {
        "net_worth_start": float(past.net_worth),
        "net_worth_end": float(latest.net_worth),
        "change_abs": float(change_abs),
        "change_pct": change_pct,
        "period_start": past.snapshot_date,
        "period_end": latest.snapshot_date,
    }
