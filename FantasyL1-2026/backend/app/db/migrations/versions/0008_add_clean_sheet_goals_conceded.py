"""add clean_sheet and goals_conceded to stats

Revision ID: 0008_add_clean_sheet_goals_conceded
Revises: 0007_add_price_movements
Create Date: 2026-01-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0008_add_clean_sheet_goals_conceded"
down_revision = "0007_add_price_movements"
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
        sa.Column("clean_sheet", sa.Integer(), nullable=True),
    )
    _add_column_if_missing(
        "player_match_stats",
        sa.Column("goals_conceded", sa.Integer(), nullable=True),
    )
    _add_column_if_missing(
        "player_round_stats",
        sa.Column("clean_sheets", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "player_round_stats",
        sa.Column("goals_conceded", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    _drop_column_if_exists("player_round_stats", "goals_conceded")
    _drop_column_if_exists("player_round_stats", "clean_sheets")
    _drop_column_if_exists("player_match_stats", "goals_conceded")
    _drop_column_if_exists("player_match_stats", "clean_sheet")
