from decimal import Decimal

from app.models.financial_snapshot import EntryType
from app.schemas.financial import FinancialEntryCreate
from app.services import financial_service, portfolio_service


def _asset(
    subcategory: str, amount: str, snapshot_date, label: str = "x", price_asset_id: str | None = None
) -> FinancialEntryCreate:
    return FinancialEntryCreate(
        entry_type=EntryType.asset,
        category="holding",
        subcategory=subcategory,
        label=label,
        amount=Decimal(amount),
        price_asset_id=price_asset_id,
        snapshot_date=snapshot_date,
    )


def test_allocation_none_without_data(db_session, test_user):
    assert portfolio_service.get_allocation(db_session, test_user.id) is None


def test_allocation_percentages_and_btc_share(db_session, test_user, today):
    financial_service.create_entry(db_session, test_user.id, _asset("cash", "2000.00", today))
    financial_service.create_entry(db_session, test_user.id, _asset("btc", "6000.00", today))
    financial_service.create_entry(db_session, test_user.id, _asset("stocks", "2000.00", today))

    result = portfolio_service.get_allocation(db_session, test_user.id)

    assert result.total_assets == Decimal("10000.00")
    assert result.btc_percent_of_assets == 60.0
    # btc share of investments only (cash excluded): 6000 / (6000 + 2000) = 75%
    assert result.btc_percent_of_investments == 75.0

    breakdown_by_sub = {item.subcategory: item.percent_of_total for item in result.breakdown}
    assert breakdown_by_sub["cash"] == 20.0
    assert breakdown_by_sub["btc"] == 60.0
    assert breakdown_by_sub["stocks"] == 20.0


def test_allocation_includes_entries_regardless_of_their_own_date(db_session, test_user, today):
    # An entry's snapshot_date is informational (e.g. purchase date), not a filter — a holding
    # dated differently from the others must still count toward the current allocation.
    from datetime import timedelta

    older = today - timedelta(days=10)
    financial_service.create_entry(db_session, test_user.id, _asset("cash", "500.00", older))
    financial_service.create_entry(db_session, test_user.id, _asset("btc", "1000.00", today))

    result = portfolio_service.get_allocation(db_session, test_user.id)

    assert result.total_assets == Decimal("1500.00")


def test_crypto_breakdown_none_without_data(db_session, test_user):
    assert portfolio_service.get_crypto_breakdown(db_session, test_user.id) is None


def test_crypto_breakdown_none_when_only_btc_held(db_session, test_user, today):
    # BTC already gets its own slice in the main allocation chart; the breakdown is only
    # for the "andere Krypto" bucket, so BTC-only holdings shouldn't produce a breakdown.
    financial_service.create_entry(db_session, test_user.id, _asset("btc", "5000.00", today))

    assert portfolio_service.get_crypto_breakdown(db_session, test_user.id) is None


def test_crypto_breakdown_groups_by_coin_id(db_session, test_user, today):
    financial_service.create_entry(
        db_session,
        test_user.id,
        _asset("crypto", "300.00", today, label="Trade Republic SOL", price_asset_id="solana"),
    )
    financial_service.create_entry(
        db_session, test_user.id, _asset("crypto", "100.00", today, label="Ledger SOL", price_asset_id="solana")
    )
    financial_service.create_entry(
        db_session, test_user.id, _asset("crypto", "600.00", today, label="Kraken ETH", price_asset_id="ethereum")
    )

    result = portfolio_service.get_crypto_breakdown(db_session, test_user.id)

    assert result.total_crypto == Decimal("1000.00")
    by_coin = {item.coin: (item.amount, item.percent_of_crypto) for item in result.breakdown}
    assert by_coin["solana"] == (Decimal("400.00"), 40.0)
    assert by_coin["ethereum"] == (Decimal("600.00"), 60.0)


def test_crypto_breakdown_falls_back_to_label_without_coin_id(db_session, test_user, today):
    financial_service.create_entry(
        db_session, test_user.id, _asset("crypto", "200.00", today, label="Mystery Altcoin", price_asset_id=None)
    )
    financial_service.create_entry(
        db_session, test_user.id, _asset("crypto", "300.00", today, label="Kraken ETH", price_asset_id="ethereum")
    )

    result = portfolio_service.get_crypto_breakdown(db_session, test_user.id)

    by_coin = {item.coin: item.amount for item in result.breakdown}
    assert by_coin["Mystery Altcoin"] == Decimal("200.00")
    assert by_coin["ethereum"] == Decimal("300.00")


def test_crypto_breakdown_includes_entries_regardless_of_their_own_date(db_session, test_user, today):
    from datetime import timedelta

    older = today - timedelta(days=5)
    financial_service.create_entry(
        db_session, test_user.id, _asset("crypto", "100.00", older, label="Old SOL", price_asset_id="solana")
    )
    financial_service.create_entry(
        db_session, test_user.id, _asset("crypto", "300.00", today, label="New ETH", price_asset_id="ethereum")
    )

    result = portfolio_service.get_crypto_breakdown(db_session, test_user.id)

    assert result.total_crypto == Decimal("400.00")
    by_coin = {item.coin: item.amount for item in result.breakdown}
    assert by_coin["solana"] == Decimal("100.00")
    assert by_coin["ethereum"] == Decimal("300.00")
