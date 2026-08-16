from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.financial_snapshot import EntryType, NetWorthSnapshot
from app.schemas.financial import FinancialEntryCreate, FinancialEntryUpdate
from app.services import financial_service


def _asset(subcategory: str, amount: str, snapshot_date: date, label: str = "test") -> FinancialEntryCreate:
    return FinancialEntryCreate(
        entry_type=EntryType.asset,
        category="holding",
        subcategory=subcategory,
        label=label,
        amount=Decimal(amount),
        snapshot_date=snapshot_date,
    )


def test_create_entry_recomputes_net_worth_snapshot(db_session, test_user, today):
    financial_service.create_entry(db_session, test_user.id, _asset("cash", "1000.00", today, "checking"))
    financial_service.create_entry(db_session, test_user.id, _asset("btc", "5000.00", today, "btc wallet"))

    snapshot = financial_service.get_current_net_worth(db_session, test_user.id)

    assert snapshot.total_assets == Decimal("6000.00")
    assert snapshot.total_liabilities == Decimal(0)
    assert snapshot.net_worth == Decimal("6000.00")
    assert snapshot.cash_total == Decimal("1000.00")
    assert snapshot.investments_total == Decimal("5000.00")


def test_liabilities_reduce_net_worth(db_session, test_user, today):
    financial_service.create_entry(db_session, test_user.id, _asset("cash", "1000.00", today))
    financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.liability,
            category="loan",
            label="car loan",
            amount=Decimal("300.00"),
            snapshot_date=today,
        ),
    )

    snapshot = financial_service.get_current_net_worth(db_session, test_user.id)

    assert snapshot.total_assets == Decimal("1000.00")
    assert snapshot.total_liabilities == Decimal("300.00")
    assert snapshot.net_worth == Decimal("700.00")


def test_income_and_expense_entries_do_not_affect_net_worth(db_session, test_user, today):
    financial_service.create_entry(db_session, test_user.id, _asset("cash", "1000.00", today))
    financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.income,
            category="salary",
            label="job",
            amount=Decimal("3000.00"),
            snapshot_date=today,
        ),
    )
    financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.expense,
            category="rent",
            label="apartment",
            amount=Decimal("1200.00"),
            snapshot_date=today,
        ),
    )

    snapshot = financial_service.get_current_net_worth(db_session, test_user.id)

    assert snapshot.net_worth == Decimal("1000.00")


def test_asset_requires_valid_subcategory(db_session, test_user, today):
    bad_entry = FinancialEntryCreate(
        entry_type=EntryType.asset,
        category="holding",
        subcategory="not_a_real_category",
        label="x",
        amount=Decimal("100.00"),
        snapshot_date=today,
    )

    with pytest.raises(ValueError, match="valid subcategory"):
        financial_service.create_entry(db_session, test_user.id, bad_entry)


def test_update_entry_amount_updates_todays_snapshot_regardless_of_entry_date(db_session, test_user, today):
    # An entry's own snapshot_date is informational (e.g. purchase date) — changing it must
    # not move the entry in or out of "today's" total, since there's only ever one row per
    # holding and net worth is always the sum of everything the user currently has.
    entry = financial_service.create_entry(db_session, test_user.id, _asset("cash", "500.00", today))
    older_date = today - timedelta(days=30)

    financial_service.update_entry(
        db_session,
        test_user.id,
        entry.id,
        FinancialEntryUpdate(snapshot_date=older_date, amount=Decimal("800.00")),
    )

    snapshot = financial_service.get_current_net_worth(db_session, test_user.id)
    assert snapshot.snapshot_date == today
    assert snapshot.net_worth == Decimal("800.00")


def test_delete_entry_recomputes_snapshot(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _asset("cash", "500.00", today))

    financial_service.delete_entry(db_session, test_user.id, entry.id)

    snapshot = financial_service.get_current_net_worth(db_session, test_user.id)
    assert snapshot.net_worth == Decimal(0)


def test_get_net_worth_change_computes_pct(db_session, test_user, today):
    # History now comes from NetWorthSnapshot rows recorded on the days a recompute actually
    # ran (see recompute_net_worth_snapshot) — not from entries dated in the past. Simulate a
    # prior recorded total directly, then let today's entry produce today's snapshot.
    earlier = today - timedelta(days=30)
    db_session.add(
        NetWorthSnapshot(
            user_id=test_user.id,
            snapshot_date=earlier,
            total_assets=Decimal("1000.00"),
            total_liabilities=Decimal(0),
            net_worth=Decimal("1000.00"),
            cash_total=Decimal("1000.00"),
            investments_total=Decimal(0),
        )
    )
    db_session.commit()
    financial_service.create_entry(db_session, test_user.id, _asset("cash", "1500.00", today))

    change = financial_service.get_net_worth_change(db_session, test_user.id, days=30)

    assert change["net_worth_start"] == 1000.00
    assert change["net_worth_end"] == 1500.00
    assert change["change_abs"] == 500.00
    assert change["change_pct"] == pytest.approx(50.0)


def test_get_net_worth_change_none_without_history(db_session, test_user, today):
    financial_service.create_entry(db_session, test_user.id, _asset("cash", "1000.00", today))

    change = financial_service.get_net_worth_change(db_session, test_user.id, days=30)

    assert change is None
