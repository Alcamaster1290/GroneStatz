from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import PaymentEvent
from app.schemas.premium import (
    ActivateManualIn,
    ActivateManualOut,
    CheckoutIntentIn,
    CheckoutIntentOut,
    SubscriptionStateOut,
)
from app.services.premium import (
    activate_manual_payment,
    build_checkout_instructions,
    create_checkout_intent,
    get_subscription_state,
)

router = APIRouter(tags=["premium"])


def _is_admin_request(x_admin_token: str | None) -> bool:
    settings = get_settings()
    return bool(x_admin_token and x_admin_token == settings.ADMIN_TOKEN)


@router.get("/me/subscription", response_model=SubscriptionStateOut)
def me_subscription(
    season_year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> SubscriptionStateOut:
    return get_subscription_state(db, user.id, season_year=season_year)


@router.post("/premium/checkout-intent", response_model=CheckoutIntentOut)
def premium_checkout_intent(
    payload: CheckoutIntentIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> CheckoutIntentOut:
    event = create_checkout_intent(
        db=db,
        user_id=user.id,
        plan_code=payload.plan_code,
        provider=payload.provider,
    )
    return CheckoutIntentOut(
        payment_event_id=event.id,
        user_id=event.user_id,
        plan_code=payload.plan_code,
        provider=payload.provider,
        amount=float(event.amount),
        currency=event.currency,
        status=event.status,  # type: ignore[arg-type]
        instructions=build_checkout_instructions(payload.provider, event.amount),
    )


@router.post("/premium/activate-manual", response_model=ActivateManualOut)
def premium_activate_manual(
    payload: ActivateManualIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> ActivateManualOut:
    settings = get_settings()
    is_admin = _is_admin_request(x_admin_token)

    payment_event = db.get(PaymentEvent, payload.payment_event_id)
    if not payment_event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment_event_not_found")

    if settings.APP_ENV == "prod" and not is_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_admin_token")
    if settings.APP_ENV != "prod" and not is_admin and payment_event.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    subscription = activate_manual_payment(
        db=db,
        payment_event=payment_event,
        provider_ref=payload.provider_ref,
    )
    return ActivateManualOut(
        ok=True,
        payment_event_id=payment_event.id,
        subscription_id=subscription.id,
        plan_code=subscription.plan_code,  # type: ignore[arg-type]
        status=subscription.status,  # type: ignore[arg-type]
    )
