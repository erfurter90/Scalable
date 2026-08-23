from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RecentTransactionOut(BaseModel):
    source: str
    asset: str
    quantity: Decimal
    price: Decimal | None
    total_cost: Decimal | None
    occurred_at: datetime | None

    model_config = {"from_attributes": True}
