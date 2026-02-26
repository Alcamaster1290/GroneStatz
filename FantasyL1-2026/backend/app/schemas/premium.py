from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


PlanCode = Literal["FREE", "PREMIUM_2R", "PREMIUM_4R", "PREMIUM_APERTURA"]
ProviderCode = Literal["yape", "stripe", "manual"]


class SubscriptionStateOut(BaseModel):
    is_premium: bool
    plan_code: PlanCode = "FREE"
    status: Literal["active", "expired", "canceled"] = "expired"
    season_year: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    start_round_id: int | None = None
    end_round_id: int | None = None
    current_round_number: int | None = None
    apertura_last_sell_round: int = 12
    apertura_total_rounds: int = 18
    can_buy_apertura: bool = True
    available_plans: list[PlanCode] = Field(default_factory=lambda: ["FREE"])


class CheckoutIntentIn(BaseModel):
    plan_code: PlanCode
    provider: ProviderCode = "manual"


class CheckoutIntentOut(BaseModel):
    payment_event_id: int
    user_id: int
    plan_code: PlanCode
    provider: ProviderCode
    amount: float
    currency: str = "PEN"
    status: Literal["pending", "paid", "failed", "refunded"] = "pending"
    instructions: str


class ActivateManualIn(BaseModel):
    payment_event_id: int = Field(gt=0)
    provider_ref: str | None = Field(default=None, max_length=120)


class ActivateManualOut(BaseModel):
    ok: bool
    payment_event_id: int
    subscription_id: int
    plan_code: PlanCode
    status: Literal["active", "expired", "canceled"]
