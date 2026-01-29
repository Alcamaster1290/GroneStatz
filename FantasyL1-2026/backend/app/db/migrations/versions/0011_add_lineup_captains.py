"""add captain fields to fantasy_lineups

Revision ID: 0011_add_lineup_captains
Revises: 0010_add_league_owner
Create Date: 2026-01-28 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_add_lineup_captains"
down_revision = "0010_add_league_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fantasy_lineups",
        sa.Column("captain_player_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "fantasy_lineups",
        sa.Column("vice_captain_player_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fantasy_lineups_captain_player_id_fkey",
        "fantasy_lineups",
        "players_catalog",
        ["captain_player_id"],
        ["player_id"],
    )
    op.create_foreign_key(
        "fantasy_lineups_vice_captain_player_id_fkey",
        "fantasy_lineups",
        "players_catalog",
        ["vice_captain_player_id"],
        ["player_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fantasy_lineups_vice_captain_player_id_fkey",
        "fantasy_lineups",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fantasy_lineups_captain_player_id_fkey",
        "fantasy_lineups",
        type_="foreignkey",
    )
    op.drop_column("fantasy_lineups", "vice_captain_player_id")
    op.drop_column("fantasy_lineups", "captain_player_id")
