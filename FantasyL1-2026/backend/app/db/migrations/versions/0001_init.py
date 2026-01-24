"""init fantasy schema

Revision ID: 0001_init
Revises: 
Create Date: 2026-01-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
    )

    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name_short", sa.String(length=50), nullable=True),
        sa.Column("name_full", sa.String(length=100), nullable=True),
    )

    op.create_table(
        "players_catalog",
        sa.Column("player_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.String(length=1), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("price_current", sa.Numeric(4, 1), nullable=False),
        sa.Column("minutesplayed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matches_played", sa.Integer(), server_default="0", nullable=False),
        sa.Column("goals", sa.Integer(), server_default="0", nullable=False),
        sa.Column("assists", sa.Integer(), server_default="0", nullable=False),
        sa.Column("saves", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fouls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "fixtures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("away_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stadium", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.UniqueConstraint("match_id"),
    )

    op.create_table(
        "fantasy_teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=True),
        sa.Column("budget_cap", sa.Numeric(5, 1), server_default="100.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "fantasy_team_players",
        sa.Column("fantasy_team_id", sa.Integer(), sa.ForeignKey("fantasy_teams.id"), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players_catalog.player_id"), primary_key=True),
        sa.Column("bought_price", sa.Numeric(4, 1), nullable=False),
        sa.Column("bought_round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "fantasy_lineups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fantasy_team_id", sa.Integer(), sa.ForeignKey("fantasy_teams.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("formation_code", sa.Text(), server_default="DEFAULT", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("fantasy_team_id", "round_id"),
    )

    op.create_table(
        "fantasy_lineup_slots",
        sa.Column("lineup_id", sa.Integer(), sa.ForeignKey("fantasy_lineups.id"), primary_key=True),
        sa.Column("slot_index", sa.Integer(), primary_key=True),
        sa.Column("is_starter", sa.Boolean(), nullable=False),
        sa.Column("role", sa.String(length=2), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players_catalog.player_id"), nullable=True),
    )

    op.create_table(
        "fantasy_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fantasy_team_id", sa.Integer(), sa.ForeignKey("fantasy_teams.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("out_player_id", sa.Integer(), sa.ForeignKey("players_catalog.player_id"), nullable=False),
        sa.Column("in_player_id", sa.Integer(), sa.ForeignKey("players_catalog.player_id"), nullable=False),
        sa.Column("out_price", sa.Numeric(4, 1), nullable=False),
        sa.Column("in_price", sa.Numeric(4, 1), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("fantasy_team_id", "round_id"),
    )

    op.create_table(
        "price_history",
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players_catalog.player_id"), primary_key=True),
        sa.Column("price", sa.Numeric(4, 1), nullable=False),
    )

    op.create_table(
        "points_round",
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players_catalog.player_id"), primary_key=True),
        sa.Column("points", sa.Numeric(6, 2), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("points_round")
    op.drop_table("price_history")
    op.drop_table("fantasy_transfers")
    op.drop_table("fantasy_lineup_slots")
    op.drop_table("fantasy_lineups")
    op.drop_table("fantasy_team_players")
    op.drop_table("fantasy_teams")
    op.drop_table("fixtures")
    op.drop_table("players_catalog")
    op.drop_table("teams")
    op.drop_table("rounds")
    op.drop_table("seasons")
    op.drop_table("users")
