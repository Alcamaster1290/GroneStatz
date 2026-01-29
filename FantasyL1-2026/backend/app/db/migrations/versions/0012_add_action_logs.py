"""add action_logs

Revision ID: 0012_add_action_logs
Revises: 0011_add_lineup_captains
Create Date: 2026-01-28 00:00:03.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_add_action_logs"
down_revision = "0011_add_lineup_captains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=True),
        sa.Column("fantasy_team_id", sa.Integer(), sa.ForeignKey("fantasy_teams.id"), nullable=True),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "target_fantasy_team_id",
            sa.Integer(),
            sa.ForeignKey("fantasy_teams.id"),
            nullable=True,
        ),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_action_logs_category", "action_logs", ["category"])
    op.create_index("ix_action_logs_league_id", "action_logs", ["league_id"])


def downgrade() -> None:
    op.drop_index("ix_action_logs_league_id", table_name="action_logs")
    op.drop_index("ix_action_logs_category", table_name="action_logs")
    op.drop_table("action_logs")
