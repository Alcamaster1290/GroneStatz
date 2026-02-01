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
    favorite_team_id: int | None = None
    rounds: List[RankingRoundOut]


class RankingOut(BaseModel):
    round_numbers: List[int]
    entries: List[RankingEntryOut]


class PublicLineupPlayerOut(BaseModel):
    player_id: int
    name: str
    short_name: str | None = None
    position: str
    team_id: int
    is_injured: bool


class PublicLineupSlotOut(BaseModel):
    slot_index: int
    is_starter: bool
    role: str
    player_id: int | None = None
    player: PublicLineupPlayerOut | None = None


class PublicLineupOut(BaseModel):
    fantasy_team_id: int
    team_name: str
    round_number: int
    captain_player_id: int | None = None
    vice_captain_player_id: int | None = None
    slots: List[PublicLineupSlotOut]
