from datetime import datetime
from typing import Optional

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
    minutesplayed: int
    matches_played: int
    goals: int
    assists: int
    saves: int
    fouls: int
    updated_at: datetime


class FixtureOut(BaseModel):
    id: int
    round_number: int
    match_id: int
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    kickoff_at: Optional[datetime] = None
    stadium: Optional[str] = None
    city: Optional[str] = None
