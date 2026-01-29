"""add leagues and league_members

Revision ID: 0009_add_leagues
Revises: 0008_add_clean_sheet_goals_conceded
Create Date: 2026-01-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_add_leagues"
down_revision = "0008_add_clean_sheet_goals_conceded"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=10), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "league_members",
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), primary_key=True),
        sa.Column(
            "fantasy_team_id",
            sa.Integer(),
            sa.ForeignKey("fantasy_teams.id"),
            primary_key=True,
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fantasy_team_id"),
    )


def downgrade() -> None:
    op.drop_table("league_members")
    op.drop_table("leagues")
