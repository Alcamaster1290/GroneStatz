from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TeamOut(BaseModel):
    id: int
    name_short: Optional[str] = None
    name_full: Optional[str] = None


class PlayerCatalogOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int
    price_current: float
    is_injured: bool
    minutesplayed: int
    matches_played: int
    goals: int
    assists: int
    saves: int
    fouls: int
    points_round: Optional[float] = None
    points_total: Optional[float] = None
    clean_sheets: Optional[int] = None
    goals_conceded: Optional[int] = None
    updated_at: datetime


class PlayerRoundPointsOut(BaseModel):
    round_number: int
    points: float


class PlayerStatsOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int
    price_current: float
    is_injured: bool
    selected_count: int
    selected_percent: float
    goals: int
    assists: int
    minutesplayed: int
    saves: int
    fouls: int
    yellow_cards: int
    red_cards: int
    rounds: List[PlayerRoundPointsOut] = []


class FixtureOut(BaseModel):
    id: int
    round_number: int
    match_id: int
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    kickoff_at: Optional[datetime] = None
    stadium: Optional[str] = None
    city: Optional[str] = None
    status: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class RoundOut(BaseModel):
    round_number: int
    is_closed: bool
    status: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
