from __future__ import annotations

from typing import List

from pydantic import BaseModel


class LeagueOut(BaseModel):
    id: int
    code: str
    name: str
    owner_fantasy_team_id: int
    is_admin: bool


class LeagueCreateIn(BaseModel):
    name: str


class LeagueJoinIn(BaseModel):
    code: str


class RankingRoundOut(BaseModel):
    round_number: int
    points: float
    cumulative: float


class RankingEntryOut(BaseModel):
    fantasy_team_id: int
    team_name: str
    total_points: float
    captain_player_id: int | None = None
    rounds: List[RankingRoundOut]


class RankingOut(BaseModel):
    round_numbers: List[int]
    entries: List[RankingEntryOut]
