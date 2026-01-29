"""add player_match_stats table

Revision ID: 0005_player_match_stats
Revises: 0004_player_round_stats
Create Date: 2026-01-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_player_match_stats"
down_revision = "0004_player_round_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_match_stats",
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), primary_key=True),
        sa.Column("match_id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players_catalog.player_id"),
            primary_key=True,
        ),
        sa.Column("minutesplayed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("saves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fouls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("player_match_stats")
