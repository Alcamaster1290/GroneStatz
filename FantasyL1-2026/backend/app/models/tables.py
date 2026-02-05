from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    is_closed = Column(Boolean, nullable=False, server_default="false")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name_short = Column(String(50), nullable=True)
    name_full = Column(String(100), nullable=True)


class PlayerCatalog(Base):
    __tablename__ = "players_catalog"

    player_id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(120), nullable=False)
    short_name = Column(String(80), nullable=True)
    position = Column(String(1), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    price_current = Column(Numeric(4, 1), nullable=False)
    minutesplayed = Column(Integer, nullable=False, server_default="0")
    matches_played = Column(Integer, nullable=False, server_default="0")
    goals = Column(Integer, nullable=False, server_default="0")
    assists = Column(Integer, nullable=False, server_default="0")
    saves = Column(Integer, nullable=False, server_default="0")
    fouls = Column(Integer, nullable=False, server_default="0")
    is_injured = Column(Boolean, nullable=False, server_default="false")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Fixture(Base):
    __tablename__ = "fixtures"

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    match_id = Column(Integer, unique=True, nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    kickoff_at = Column(DateTime(timezone=True), nullable=True)
    stadium = Column(String(120), nullable=True)
    city = Column(String(120), nullable=True)
    status = Column(String(20), nullable=False, server_default="Programado")
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)


class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    name = Column(String(60), nullable=True)
    favorite_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    budget_cap = Column(Numeric(5, 1), nullable=False, server_default="100.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FantasyTeamPlayer(Base):
    __tablename__ = "fantasy_team_players"

    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players_catalog.player_id"), primary_key=True)
    bought_price = Column(Numeric(4, 1), nullable=False)
    bought_round_id = Column(Integer, ForeignKey("rounds.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")


class FantasyLineup(Base):
    __tablename__ = "fantasy_lineups"

    id = Column(Integer, primary_key=True)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    formation_code = Column(Text, nullable=False, server_default="DEFAULT")
    captain_player_id = Column(Integer, ForeignKey("players_catalog.player_id"), nullable=True)
    vice_captain_player_id = Column(Integer, ForeignKey("players_catalog.player_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("fantasy_team_id", "round_id"),)


class FantasyLineupSlot(Base):
    __tablename__ = "fantasy_lineup_slots"

    lineup_id = Column(Integer, ForeignKey("fantasy_lineups.id"), primary_key=True)
    slot_index = Column(Integer, primary_key=True)
    is_starter = Column(Boolean, nullable=False)
    role = Column(String(2), nullable=False)
    player_id = Column(Integer, ForeignKey("players_catalog.player_id"), nullable=True)


class FantasyTransfer(Base):
    __tablename__ = "fantasy_transfers"

    id = Column(Integer, primary_key=True)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    out_player_id = Column(Integer, ForeignKey("players_catalog.player_id"), nullable=False)
    in_player_id = Column(Integer, ForeignKey("players_catalog.player_id"), nullable=False)
    out_price = Column(Numeric(4, 1), nullable=False)
    in_price = Column(Numeric(4, 1), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PriceHistory(Base):
    __tablename__ = "price_history"

    season_id = Column(Integer, ForeignKey("seasons.id"), primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players_catalog.player_id"), primary_key=True)
    price = Column(Numeric(4, 1), nullable=False)


class PriceMovement(Base):
    __tablename__ = "price_movements"

    season_id = Column(Integer, ForeignKey("seasons.id"), primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players_catalog.player_id"), primary_key=True)
    points = Column(Numeric(6, 2), nullable=False)
    delta = Column(Numeric(4, 1), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True)
    code = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(80), nullable=False)
    owner_fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False)
    is_public = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LeagueMember(Base):
    __tablename__ = "league_members"

    league_id = Column(Integer, ForeignKey("leagues.id"), primary_key=True)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), primary_key=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("fantasy_team_id"),)


class PointsRound(Base):
    __tablename__ = "points_round"

    season_id = Column(Integer, ForeignKey("seasons.id"), primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players_catalog.player_id"), primary_key=True)
    points = Column(Numeric(6, 2), nullable=False, server_default="0")


class PlayerRoundStat(Base):
    __tablename__ = "player_round_stats"

    season_id = Column(Integer, ForeignKey("seasons.id"), primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players_catalog.player_id"), primary_key=True)
    minutesplayed = Column(Integer, nullable=False, server_default="0")
    goals = Column(Integer, nullable=False, server_default="0")
    assists = Column(Integer, nullable=False, server_default="0")
    saves = Column(Integer, nullable=False, server_default="0")
    fouls = Column(Integer, nullable=False, server_default="0")
    yellow_cards = Column(Integer, nullable=False, server_default="0")
    red_cards = Column(Integer, nullable=False, server_default="0")
    clean_sheets = Column(Integer, nullable=False, server_default="0")
    goals_conceded = Column(Integer, nullable=False, server_default="0")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PlayerMatchStat(Base):
    __tablename__ = "player_match_stats"

    season_id = Column(Integer, ForeignKey("seasons.id"), primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), primary_key=True)
    match_id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players_catalog.player_id"), primary_key=True)
    minutesplayed = Column(Integer, nullable=False, server_default="0")
    goals = Column(Integer, nullable=False, server_default="0")
    assists = Column(Integer, nullable=False, server_default="0")
    saves = Column(Integer, nullable=False, server_default="0")
    fouls = Column(Integer, nullable=False, server_default="0")
    yellow_cards = Column(Integer, nullable=False, server_default="0")
    red_cards = Column(Integer, nullable=False, server_default="0")
    clean_sheet = Column(Integer, nullable=True)
    goals_conceded = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True)
    category = Column(String(30), nullable=False)
    action = Column(String(50), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    target_fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(128), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PushDeviceToken(Base):
    __tablename__ = "push_device_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String(20), nullable=False)
    device_id = Column(String(191), nullable=False)
    token = Column(Text, nullable=False)
    timezone = Column(String(64), nullable=True)
    app_channel = Column(String(30), nullable=False, server_default="mobile")
    app_version = Column(String(40), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("user_id", "device_id"),)


class RoundPushNotification(Base):
    __tablename__ = "round_push_notifications"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False, index=True)
    device_token_id = Column(
        Integer, ForeignKey("push_device_tokens.id"), nullable=False, index=True
    )
    notification_type = Column(String(40), nullable=False, server_default="round_deadline")
    status = Column(String(20), nullable=False, server_default="pending")
    error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("round_id", "device_token_id", "notification_type"),
    )
