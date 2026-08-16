from decimal import Decimal

from pydantic import BaseModel


class BitvavoStatusOut(BaseModel):
    configured: bool


class BitvavoAssetResultOut(BaseModel):
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


class BitvavoSyncResultOut(BaseModel):
    configured: bool
    assets: list[BitvavoAssetResultOut]
    error: str | None

    model_config = {"from_attributes": True}
