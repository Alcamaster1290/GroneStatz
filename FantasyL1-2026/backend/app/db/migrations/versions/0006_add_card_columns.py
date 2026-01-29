"""add card columns to player stats tables

Revision ID: 0006_add_card_columns
Revises: 0005_player_match_stats
Create Date: 2026-01-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0006_add_card_columns"
down_revision = "0005_player_match_stats"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name in columns:
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    _add_column_if_missing(
        "player_match_stats",
        sa.Column("yellow_cards", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "player_match_stats",
        sa.Column("red_cards", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "player_round_stats",
        sa.Column("yellow_cards", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "player_round_stats",
        sa.Column("red_cards", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    _drop_column_if_exists("player_round_stats", "red_cards")
    _drop_column_if_exists("player_round_stats", "yellow_cards")
    _drop_column_if_exists("player_match_stats", "red_cards")
    _drop_column_if_exists("player_match_stats", "yellow_cards")
