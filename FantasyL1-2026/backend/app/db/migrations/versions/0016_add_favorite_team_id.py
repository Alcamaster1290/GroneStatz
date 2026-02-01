"""add favorite team id to fantasy teams

Revision ID: 0016_add_favorite_team_id
Revises: 0015_add_player_injury_status
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_add_favorite_team_id"
down_revision = "0015_add_player_injury_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fantasy_teams", sa.Column("favorite_team_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fantasy_teams_favorite_team_id_fkey",
        "fantasy_teams",
        "teams",
        ["favorite_team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fantasy_teams_favorite_team_id_fkey", "fantasy_teams", type_="foreignkey")
    op.drop_column("fantasy_teams", "favorite_team_id")
