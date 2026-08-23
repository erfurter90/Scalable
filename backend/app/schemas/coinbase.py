from decimal import Decimal

from pydantic import BaseModel


class CoinbaseStatusOut(BaseModel):
    configured: bool


class CoinbaseAssetResultOut(BaseModel):
    symbol: str
    coingecko_id: str | None
    quantity: Decimal
    average_cost_basis: Decimal | None
    cost_basis_incomplete: bool
    current_value_eur: Decimal | None
    replaced_entry_labels: list[str]
    note: str | None
    error: str | None

    model_config = {"from_attributes": True}


class CoinbaseSyncResultOut(BaseModel):
    configured: bool
    assets: list[CoinbaseAssetResultOut]
    error: str | None

    model_config = {"from_attributes": True}
