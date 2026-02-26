from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.premium import PlanCode


class PublicLeaderboardEntryOut(BaseModel):
    rank: int
    fantasy_team_id: int
    team_name: str
    points_total: float


class PublicLeaderboardOut(BaseModel):
    season_year: int
    limit: int
    entries: list[PublicLeaderboardEntryOut]


class PublicPremiumPricesOut(BaseModel):
    PREMIUM_2R: float
    PREMIUM_4R: float
    PREMIUM_APERTURA: float


class PublicPremiumConfigOut(BaseModel):
    season_year: int
    current_round_number: int | None = None
    apertura_last_sell_round: int
    apertura_total_rounds: int
    can_buy_apertura: bool
    available_plans: list[PlanCode]
    prices: PublicPremiumPricesOut


class PublicPremiumBadgeOut(BaseModel):
    enabled: bool = True
    text: str = "P"
    color: str = "#7C3AED"
    shape: Literal["circle", "rounded"] = "circle"


class PublicAppConfigOut(BaseModel):
    premium_badge: PublicPremiumBadgeOut
