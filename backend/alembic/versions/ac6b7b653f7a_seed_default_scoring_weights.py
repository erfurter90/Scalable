"""seed default scoring weights

Revision ID: ac6b7b653f7a
Revises: 2d971a3ff7ee
Create Date: 2026-08-16 10:52:45.596290

"""
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
import yaml

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ac6b7b653f7a'
down_revision: str | Sequence[str] | None = '2d971a3ff7ee'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Minimal ad-hoc table description (not the ORM model) — Alembic data migrations should not
# import app models directly, since the model's Python definition can drift from what a given
# historical migration needs to write. This mirrors scoring_config.py at the time of writing.
scoring_weights_configs = sa.table(
    "scoring_weights_configs",
    sa.column("id", sa.Integer),
    sa.column("version", sa.Integer),
    sa.column("valuation_weight", sa.Numeric(4, 3)),
    sa.column("sentiment_weight", sa.Numeric(4, 3)),
    sa.column("cycle_weight", sa.Numeric(4, 3)),
    sa.column("macro_weight", sa.Numeric(4, 3)),
    sa.column("momentum_weight", sa.Numeric(4, 3)),
    sa.column("onchain_weight", sa.Numeric(4, 3)),
    sa.column("is_active", sa.Boolean),
)

DEFAULT_WEIGHTS_FILE = Path(__file__).resolve().parents[2] / "app" / "config" / "default_scoring_weights.yaml"


def upgrade() -> None:
    weights = yaml.safe_load(DEFAULT_WEIGHTS_FILE.read_text())
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Default scoring weights must sum to 1.0, got {total}")

    op.bulk_insert(
        scoring_weights_configs,
        [
            {
                "version": 1,
                "valuation_weight": weights["valuation_weight"],
                "sentiment_weight": weights["sentiment_weight"],
                "cycle_weight": weights["cycle_weight"],
                "macro_weight": weights["macro_weight"],
                "momentum_weight": weights["momentum_weight"],
                "onchain_weight": weights["onchain_weight"],
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute(scoring_weights_configs.delete().where(scoring_weights_configs.c.version == 1))
