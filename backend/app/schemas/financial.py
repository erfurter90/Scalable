from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.financial_snapshot import EntryType

PurchaseCurrency = Literal["EUR", "USD"]


class FinancialEntryCreate(BaseModel):
    entry_type: EntryType
    category: str = Field(min_length=1, max_length=64)
    subcategory: str | None = Field(default=None, max_length=32)
    label: str = Field(min_length=1, max_length=128)
    # Either provide `amount` directly, or `quantity` + `price_asset_id` and let the backend
    # compute the EUR value from the live price (e.g. 0.2 BTC instead of a manually
    # calculated, immediately-stale "5000 EUR").
    amount: Decimal | None = Field(default=None, gt=0)
    quantity: Decimal | None = Field(default=None, gt=0)
    price_asset_id: str | None = Field(default=None, max_length=64)
    currency: str = Field(default="EUR", min_length=3, max_length=8)
    # Optional: what was paid per unit for this (first) purchase, seeding the average
    # acquisition cost basis. Only meaningful together with quantity/price_asset_id.
    purchase_price: Decimal | None = Field(default=None, gt=0)
    purchase_price_currency: PurchaseCurrency | None = None
    snapshot_date: date
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_amount_or_quantity(self) -> "FinancialEntryCreate":
        if self.amount is None and (self.quantity is None or not self.price_asset_id):
            raise ValueError("Either 'amount', or both 'quantity' and 'price_asset_id', must be provided.")
        if self.purchase_price is not None and (self.quantity is None or not self.price_asset_id):
            raise ValueError("'purchase_price' requires both 'quantity' and 'price_asset_id' to be set.")
        return self


class FinancialEntryUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=64)
    subcategory: str | None = Field(default=None, max_length=32)
    label: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(default=None, gt=0)
    quantity: Decimal | None = Field(default=None, gt=0)
    price_asset_id: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    snapshot_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class FinancialEntryOut(BaseModel):
    id: int
    entry_type: EntryType
    category: str
    subcategory: str | None
    label: str
    amount: Decimal
    quantity: Decimal | None
    price_asset_id: str | None
    average_cost_basis: Decimal | None
    currency: str
    snapshot_date: date
    notes: str | None
    source: str

    model_config = {"from_attributes": True}


class PurchaseCreate(BaseModel):
    """Body for POST /entries/{id}/add-purchase — records buying more of an existing
    quantity-tracked holding, blending the new price into the running average cost basis."""

    additional_quantity: Decimal = Field(gt=0)
    purchase_price: Decimal = Field(gt=0)
    purchase_price_currency: PurchaseCurrency = "EUR"


class CostBasisSet(BaseModel):
    """Body for POST /entries/{id}/set-cost-basis — records what was paid, on average, for
    the entry's *current* quantity (e.g. a holding that was quantity-tracked from the start
    without ever recording a purchase price). Unlike add-purchase, this does not change the
    quantity and does not blend with any prior average — it replaces it outright."""

    purchase_price: Decimal = Field(gt=0)
    purchase_price_currency: PurchaseCurrency = "EUR"


class NetWorthSnapshotOut(BaseModel):
    snapshot_date: date
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    cash_total: Decimal
    investments_total: Decimal

    model_config = {"from_attributes": True}


class NetWorthChangeOut(BaseModel):
    net_worth_start: float
    net_worth_end: float
    change_abs: float
    change_pct: float | None
    period_start: date
    period_end: date
