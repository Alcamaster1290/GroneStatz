from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class AdminTeamPlayerOut(BaseModel):
    player_id: int
    name: str
    short_name: Optional[str] = None
    position: str
    team_id: int
    price_current: float
    bought_price: float


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
