from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FantasyTeamCreate(BaseModel):
    name: Optional[str] = None


class FantasyTeamPlayerOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int
    price_current: float
    bought_price: float


class FantasyTeamOut(BaseModel):
    id: int
    name: Optional[str]
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
    slots: List[LineupSlotIn]


class LineupUpdateIn(BaseModel):
    slots: List[LineupSlotIn]


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


class ValidationResult(BaseModel):
    ok: bool
    errors: List[str]
