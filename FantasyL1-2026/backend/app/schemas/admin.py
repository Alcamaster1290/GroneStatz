from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel

FixtureStatus = Literal["Programado", "Postergado", "Finalizado"]


class AdminTeamPlayerOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int
    price_current: float
    bought_price: float
    is_injured: bool


class AdminTeamOut(BaseModel):
    fantasy_team_id: int
    user_id: int
    user_email: str
    season_id: int
    name: Optional[str]
    budget_cap: float
    budget_used: float
    budget_left: float
    club_counts: Dict[int, int]
    squad: List[AdminTeamPlayerOut]


class AdminLineupPlayerOut(BaseModel):
    player_id: Optional[int] = None
    name: Optional[str] = None
    short_name: Optional[str] = None
    position: Optional[str] = None
    team_id: Optional[int] = None
    is_injured: Optional[bool] = None


class AdminLineupSlotOut(BaseModel):
    slot_index: int
    is_starter: bool
    role: str
    player_id: Optional[int] = None
    player: Optional[AdminLineupPlayerOut] = None


class AdminTeamLineupOut(BaseModel):
    fantasy_team_id: int
    team_name: Optional[str] = None
    user_email: str
    round_number: int
    lineup_id: int
    created_at: datetime
    captain_player_id: Optional[int] = None
    vice_captain_player_id: Optional[int] = None
    slots: List[AdminLineupSlotOut]


class AdminFixtureBase(BaseModel):
    round_number: int
    match_id: int
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    kickoff_at: Optional[str] = None
    stadium: Optional[str] = None
    city: Optional[str] = None
    status: Optional[FixtureStatus] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class AdminFixtureCreate(AdminFixtureBase):
    pass


class AdminFixtureUpdate(BaseModel):
    round_number: Optional[int] = None
    match_id: Optional[int] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    kickoff_at: Optional[str] = None
    stadium: Optional[str] = None
    city: Optional[str] = None
    status: Optional[FixtureStatus] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class AdminFixtureOut(BaseModel):
    id: int
    round_number: int
    match_id: int
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    kickoff_at: Optional[datetime] = None
    stadium: Optional[str] = None
    city: Optional[str] = None
    status: FixtureStatus
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class AdminPlayerStatIn(BaseModel):
    player_id: int
    match_id: int
    minutesplayed: Optional[int] = 0
    goals: Optional[int] = 0
    assists: Optional[int] = 0
    saves: Optional[int] = 0
    fouls: Optional[int] = 0
    yellow_cards: Optional[int] = 0
    red_cards: Optional[int] = 0
    clean_sheet: Optional[int] = None
    goals_conceded: Optional[int] = None


class AdminPlayerRoundStatsIn(BaseModel):
    round_number: int
    items: List[AdminPlayerStatIn]


class AdminPlayerStatOut(BaseModel):
    round_number: int
    match_id: int
    player_id: int
    minutesplayed: int
    goals: int
    assists: int
    saves: int
    fouls: int
    yellow_cards: int
    red_cards: int
    clean_sheet: Optional[int] = None
    goals_conceded: Optional[int] = None


class AdminPriceMovementOut(BaseModel):
    round_number: int
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int
    price_current: float
    points: float
    delta: float


class AdminTransferPlayerOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int


class AdminTransferOut(BaseModel):
    id: int
    fantasy_team_id: int
    team_name: Optional[str] = None
    user_email: str
    round_number: int
    created_at: datetime
    out_player: Optional[AdminTransferPlayerOut] = None
    in_player: Optional[AdminTransferPlayerOut] = None
    out_price: float
    in_price: float
    out_price_current: float
    in_price_current: float
    transfer_fee: float
    budget_after: float


class AdminMatchPlayerOut(BaseModel):
    match_id: int
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: Optional[str] = None
    team_id: Optional[int] = None
    minutesplayed: int
    goals: int
    assists: int
    saves: int
    fouls: int
    yellow_cards: int
    red_cards: int
    clean_sheet: Optional[int] = None
    goals_conceded: Optional[int] = None
    points: float

class AdminRoundTopPlayerOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: Optional[str] = None
    team_id: Optional[int] = None
    points: float

class AdminRoundOut(BaseModel):
    id: int
    round_number: int
    is_closed: bool
    status: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class AdminRoundWindowUpdateIn(BaseModel):
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class AdminLeagueMemberOut(BaseModel):
    fantasy_team_id: int
    team_name: Optional[str] = None
    user_email: str
    joined_at: datetime


class AdminLeagueOut(BaseModel):
    id: int
    code: str
    name: str
    owner_fantasy_team_id: int
    created_at: datetime
    members: List[AdminLeagueMemberOut]


class AdminActionLogOut(BaseModel):
    id: int
    category: str
    action: str
    created_at: datetime
    actor_user_id: Optional[int] = None
    actor_email: Optional[str] = None
    league_id: Optional[int] = None
    fantasy_team_id: Optional[int] = None
    target_user_id: Optional[int] = None
    target_fantasy_team_id: Optional[int] = None
    details: Optional[str] = None


class AdminPlayerInjuryIn(BaseModel):
    is_injured: bool


class AdminPlayerInjuryOut(BaseModel):
    player_id: int
    is_injured: bool


class AdminPlayerListItem(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: Optional[int] = None
    is_injured: bool


class AdminPlayerListOut(BaseModel):
    total: int
    injured: int
    unselected: int
    items: List[AdminPlayerListItem]
