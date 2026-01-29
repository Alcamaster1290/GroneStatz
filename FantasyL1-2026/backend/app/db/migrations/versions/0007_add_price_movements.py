"""add price_movements table

Revision ID: 0007_add_price_movements
Revises: 0006_add_card_columns
Create Date: 2026-01-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_add_price_movements"
down_revision = "0006_add_card_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_movements",
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players_catalog.player_id"),
            primary_key=True,
        ),
        sa.Column("points", sa.Numeric(6, 2), nullable=False),
        sa.Column("delta", sa.Numeric(4, 1), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("price_movements")
