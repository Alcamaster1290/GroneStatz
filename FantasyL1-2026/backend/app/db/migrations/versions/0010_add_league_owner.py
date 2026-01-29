"""add owner to leagues

Revision ID: 0010_add_league_owner
Revises: 0009_add_leagues
Create Date: 2026-01-28 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010_add_league_owner"
down_revision = "0009_add_leagues"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leagues",
        sa.Column("owner_fantasy_team_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "leagues_owner_fantasy_team_id_fkey",
        "leagues",
        "fantasy_teams",
        ["owner_fantasy_team_id"],
        ["id"],
    )
    op.execute(
        """
        UPDATE leagues
        SET owner_fantasy_team_id = members.fantasy_team_id
        FROM (
            SELECT DISTINCT ON (league_id) league_id, fantasy_team_id
            FROM league_members
            ORDER BY league_id, joined_at
        ) AS members
        WHERE leagues.id = members.league_id
        """
    )
    op.execute("DELETE FROM leagues WHERE owner_fantasy_team_id IS NULL")
    op.alter_column("leagues", "owner_fantasy_team_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("leagues_owner_fantasy_team_id_fkey", "leagues", type_="foreignkey")
    op.drop_column("leagues", "owner_fantasy_team_id")
