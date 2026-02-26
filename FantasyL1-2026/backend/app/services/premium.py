from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppConfig, PaymentEvent, Round, Season, Subscription
from app.schemas.premium import PlanCode, ProviderCode, SubscriptionStateOut
from app.services.fantasy import get_current_round, get_latest_round, get_or_create_season

ActiveStatus = Literal["active", "expired", "canceled"]

PLAN_PRICES: dict[str, Decimal] = {
    "PREMIUM_2R": Decimal("29.90"),
    "PREMIUM_4R": Decimal("49.90"),
    "PREMIUM_APERTURA": Decimal("120.00"),
}
ALLOWED_PREMIUM_PLANS: set[str] = {"PREMIUM_2R", "PREMIUM_4R", "PREMIUM_APERTURA"}
APERTURA_MAX_PRICE = Decimal("120.00")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_config_value(db: Session, key: str, default: str) -> str:
    row = db.execute(select(AppConfig.value).where(AppConfig.key == key)).scalar_one_or_none()
    return str(row) if row is not None else default


def get_config_int(db: Session, key: str, default: int) -> int:
    raw = get_config_value(db, key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_or_create_season_by_year(db: Session, season_year: int) -> Season:
    season = db.execute(select(Season).where(Season.year == season_year)).scalar_one_or_none()
    if season:
        return season
    settings = get_settings()
    if season_year == settings.SEASON_YEAR:
        return get_or_create_season(db)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="season_not_found")


def get_current_round_for_season(db: Session, season_id: int) -> Round | None:
    round_obj = get_current_round(db, season_id)
    if round_obj:
        return round_obj
    return get_latest_round(db, season_id)


def _validate_apertura_sell_window(
    plan_code: str,
    current_round_number: int | None,
    last_sell_round: int,
) -> None:
    if plan_code != "PREMIUM_APERTURA":
        return
    if current_round_number is None:
        return
    if current_round_number > last_sell_round:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="premium_apertura_not_available_after_round",
        )


def _resolve_end_round_number(
    plan_code: str,
    current_round_number: int,
    apertura_total_rounds: int,
) -> int:
    if plan_code == "PREMIUM_2R":
        return current_round_number + 1
    if plan_code == "PREMIUM_4R":
        return current_round_number + 3
    if plan_code == "PREMIUM_APERTURA":
        return apertura_total_rounds
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plan_not_supported")


def _build_available_plans(can_buy_apertura: bool) -> list[PlanCode]:
    plans: list[PlanCode] = ["FREE", "PREMIUM_2R", "PREMIUM_4R"]
    if can_buy_apertura:
        plans.append("PREMIUM_APERTURA")
    return plans


def _resolve_round_for_number(db: Session, season_id: int, round_number: int) -> Round:
    round_obj = db.execute(
        select(Round).where(Round.season_id == season_id, Round.round_number == round_number)
    ).scalar_one_or_none()
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="round_not_found")
    return round_obj


def _cancel_active_subscriptions(db: Session, user_id: int) -> None:
    db.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
        .values(status="canceled", updated_at=_now_utc())
    )


def _is_subscription_expired(
    subscription: Subscription,
    current_round_number: int | None,
    end_round_number: int | None,
    now: datetime,
) -> bool:
    if subscription.status != "active":
        return True
    if subscription.ends_at and now > subscription.ends_at:
        return True
    if (
        current_round_number is not None
        and end_round_number is not None
        and current_round_number > end_round_number
    ):
        return True
    return False


def _fetch_active_subscription(
    db: Session,
    user_id: int,
    season_id: int | None = None,
) -> Subscription | None:
    query = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "active",
    )
    if season_id is not None:
        query = query.where(Subscription.season_id == season_id)
    return db.execute(query.order_by(Subscription.created_at.desc())).scalars().first()


def get_subscription_state(
    db: Session,
    user_id: int,
    season_year: int | None = None,
) -> SubscriptionStateOut:
    settings = get_settings()
    target_season_year = season_year or settings.SEASON_YEAR
    season = get_or_create_season_by_year(db, target_season_year)
    current_round = get_current_round_for_season(db, season.id)
    current_round_number = current_round.round_number if current_round else None
    last_sell_round = get_config_int(db, "APERTURA_PREMIUM_LAST_SELL_ROUND", 12)
    apertura_total_rounds = get_config_int(db, "APERTURA_TOTAL_ROUNDS", 18)
    can_buy_apertura = (
        current_round_number is None or current_round_number <= last_sell_round
    )
    available_plans = _build_available_plans(can_buy_apertura)

    subscription = _fetch_active_subscription(db, user_id=user_id, season_id=season.id)
    if not subscription:
        return SubscriptionStateOut(
            is_premium=False,
            plan_code="FREE",
            status="expired",
            season_year=target_season_year,
            current_round_number=current_round_number,
            apertura_last_sell_round=last_sell_round,
            apertura_total_rounds=apertura_total_rounds,
            can_buy_apertura=can_buy_apertura,
            available_plans=available_plans,
        )

    end_round_number = None
    if subscription.end_round_id:
        end_round_number = db.execute(
            select(Round.round_number).where(Round.id == subscription.end_round_id)
        ).scalar_one_or_none()

    now = _now_utc()
    if _is_subscription_expired(subscription, current_round_number, end_round_number, now):
        subscription.status = "expired"
        subscription.updated_at = now
        db.commit()
        return SubscriptionStateOut(
            is_premium=False,
            plan_code="FREE",
            status="expired",
            season_year=target_season_year,
            current_round_number=current_round_number,
            apertura_last_sell_round=last_sell_round,
            apertura_total_rounds=apertura_total_rounds,
            can_buy_apertura=can_buy_apertura,
            available_plans=available_plans,
        )

    return SubscriptionStateOut(
        is_premium=subscription.plan_code != "FREE",
        plan_code=subscription.plan_code,  # type: ignore[arg-type]
        status=subscription.status,  # type: ignore[arg-type]
        season_year=target_season_year,
        starts_at=subscription.starts_at,
        ends_at=subscription.ends_at,
        start_round_id=subscription.start_round_id,
        end_round_id=subscription.end_round_id,
        current_round_number=current_round_number,
        apertura_last_sell_round=last_sell_round,
        apertura_total_rounds=apertura_total_rounds,
        can_buy_apertura=can_buy_apertura,
        available_plans=available_plans,
    )


def create_checkout_intent(
    db: Session,
    user_id: int,
    plan_code: PlanCode,
    provider: ProviderCode,
) -> PaymentEvent:
    if plan_code not in ALLOWED_PREMIUM_PLANS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plan_not_supported")

    settings = get_settings()
    season = get_or_create_season(db)
    current_round = get_current_round_for_season(db, season.id)
    current_round_number = current_round.round_number if current_round else None

    last_sell_round = get_config_int(db, "APERTURA_PREMIUM_LAST_SELL_ROUND", 12)
    _validate_apertura_sell_window(plan_code, current_round_number, last_sell_round)

    amount = PLAN_PRICES[plan_code]
    if plan_code == "PREMIUM_APERTURA" and amount > APERTURA_MAX_PRICE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="premium_apertura_price_exceeded",
        )
    event = PaymentEvent(
        user_id=user_id,
        provider=provider,
        amount=amount,
        currency="PEN",
        status="pending",
        meta={
            "plan_code": plan_code,
            "season_year": season.year,
            "season_id": season.id,
            "current_round_number": current_round_number,
            "app_env": settings.APP_ENV,
        },
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def activate_manual_payment(
    db: Session,
    payment_event: PaymentEvent,
    provider_ref: str | None = None,
) -> Subscription:
    if payment_event.status == "paid" and payment_event.subscription_id:
        existing = db.get(Subscription, payment_event.subscription_id)
        if existing:
            return existing

    metadata = payment_event.meta or {}
    plan_code = metadata.get("plan_code")
    if plan_code not in ALLOWED_PREMIUM_PLANS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plan_not_supported")

    season_id = metadata.get("season_id")
    season = db.get(Season, int(season_id)) if season_id else get_or_create_season(db)
    if not season:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="season_not_found")

    current_round = get_current_round_for_season(db, season.id)
    if not current_round:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="round_not_found")

    last_sell_round = get_config_int(db, "APERTURA_PREMIUM_LAST_SELL_ROUND", 12)
    _validate_apertura_sell_window(plan_code, current_round.round_number, last_sell_round)

    apertura_total_rounds = get_config_int(db, "APERTURA_TOTAL_ROUNDS", 18)
    end_round_number = _resolve_end_round_number(
        plan_code=plan_code,
        current_round_number=current_round.round_number,
        apertura_total_rounds=apertura_total_rounds,
    )
    end_round = _resolve_round_for_number(db, season.id, end_round_number)

    now = _now_utc()
    _cancel_active_subscriptions(db, payment_event.user_id)

    subscription = Subscription(
        user_id=payment_event.user_id,
        season_id=season.id,
        status="active",
        plan_code=plan_code,
        starts_at=now,
        ends_at=None,
        start_round_id=current_round.id,
        end_round_id=end_round.id,
        created_at=now,
        updated_at=now,
    )
    db.add(subscription)
    db.flush()

    payment_event.subscription_id = subscription.id
    payment_event.status = "paid"
    if provider_ref:
        payment_event.provider_ref = provider_ref

    db.commit()
    db.refresh(subscription)
    return subscription


def build_checkout_instructions(provider: ProviderCode, amount: Decimal) -> str:
    amount_str = f"S/{amount:.2f}"
    if provider == "yape":
        return f"Paga por Yape ({amount_str}) y comparte el comprobante para activacion manual."
    if provider == "stripe":
        return f"Checkout Stripe en construccion. Monto referencial: {amount_str}."
    return f"Pago manual habilitado en test. Monto registrado: {amount_str}."


def get_public_premium_config(
    db: Session,
    season_year: int | None = None,
) -> dict:
    settings = get_settings()
    target_season_year = season_year or settings.SEASON_YEAR
    season = get_or_create_season_by_year(db, target_season_year)
    current_round = get_current_round_for_season(db, season.id)
    current_round_number = current_round.round_number if current_round else None
    last_sell_round = get_config_int(db, "APERTURA_PREMIUM_LAST_SELL_ROUND", 12)
    apertura_total_rounds = get_config_int(db, "APERTURA_TOTAL_ROUNDS", 18)
    can_buy_apertura = (
        current_round_number is None or current_round_number <= last_sell_round
    )
    return {
        "season_year": target_season_year,
        "current_round_number": current_round_number,
        "apertura_last_sell_round": last_sell_round,
        "apertura_total_rounds": apertura_total_rounds,
        "can_buy_apertura": can_buy_apertura,
        "available_plans": _build_available_plans(can_buy_apertura),
        "prices": {
            "PREMIUM_2R": float(PLAN_PRICES["PREMIUM_2R"]),
            "PREMIUM_4R": float(PLAN_PRICES["PREMIUM_4R"]),
            "PREMIUM_APERTURA": float(PLAN_PRICES["PREMIUM_APERTURA"]),
        },
    }
