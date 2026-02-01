from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FantasyTeamCreate(BaseModel):
    name: Optional[str] = None


class FavoriteTeamUpdateIn(BaseModel):
    team_id: int


class FantasyTeamPlayerOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int
    price_current: float
    bought_price: float
    is_injured: bool
    goals: int = 0
    assists: int = 0
    saves: int = 0
    points_round: Optional[float] = None
    clean_sheets: Optional[int] = None
    goals_conceded: Optional[int] = None


class FantasyTeamOut(BaseModel):
    id: int
    name: Optional[str]
    favorite_team_id: Optional[int] = None
    budget_cap: float
    budget_used: float
    budget_left: float
    club_counts: Dict[int, int]
    squad: List[FantasyTeamPlayerOut]


class SquadUpdateIn(BaseModel):
    player_ids: List[int] = Field(min_length=15, max_length=15)


class LineupSlotIn(BaseModel):
    slot_index: int
    is_starter: bool
    role: str
    player_id: Optional[int] = None


class LineupOut(BaseModel):
    lineup_id: int
    round_number: int
    is_closed: bool
    captain_player_id: Optional[int] = None
    vice_captain_player_id: Optional[int] = None
    slots: List[LineupSlotIn]


class LineupUpdateIn(BaseModel):
    slots: List[LineupSlotIn]
    captain_player_id: Optional[int] = None
    vice_captain_player_id: Optional[int] = None
    reset: bool = False


class TransferIn(BaseModel):
    out_player_id: int
    in_player_id: int


class TransferOut(BaseModel):
    id: int
    fantasy_team_id: int
    round_id: int
    out_player_id: int
    in_player_id: int
    out_price: float
    in_price: float
    created_at: datetime


class TransferCountOut(BaseModel):
    round_number: int
    transfers_used: int
    next_fee: float


class ValidationResult(BaseModel):
    ok: bool
    errors: List[str]
    message: Optional[str] = None
