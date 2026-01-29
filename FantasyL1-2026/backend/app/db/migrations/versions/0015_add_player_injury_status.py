"""add is_injured to players_catalog

Revision ID: 0015_add_player_injury_status
Revises: 0014_drop_transfer_unique_add_transfer_fees
Create Date: 2026-01-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0015_add_player_injury_status"
down_revision = "0014_drop_transfer_unique_add_transfer_fees"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players_catalog",
        sa.Column("is_injured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("players_catalog", "is_injured")
