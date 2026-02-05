from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.notifications import (
    PushDeviceDeleteOut,
    PushDeviceOut,
    PushDeviceRegisterIn,
    PushDeviceRegisterOut,
)
from app.services.action_log import log_action
from app.services.push_notifications import (
    deactivate_user_device,
    list_user_devices,
    register_user_device,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/devices", response_model=List[PushDeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[PushDeviceOut]:
    rows = list_user_devices(db, user.id)
    return [
        PushDeviceOut(
            id=row.id,
            user_id=row.user_id,
            platform=row.platform,  # type: ignore[arg-type]
            device_id=row.device_id,
            token=row.token,
            timezone=row.timezone,
            app_channel=row.app_channel,
            app_version=row.app_version,
            is_active=bool(row.is_active),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.post("/devices/register", response_model=PushDeviceRegisterOut)
def register_device(
    payload: PushDeviceRegisterIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PushDeviceRegisterOut:
    row = register_user_device(db, user_id=user.id, payload=payload)
    log_action(
        db,
        category="notifications",
        action="register_token",
        actor_user_id=user.id,
        details={
            "device_id": payload.device_id,
            "platform": payload.platform,
            "app_channel": payload.app_channel,
            "active": True,
        },
    )
    return PushDeviceRegisterOut(
        ok=True,
        device=PushDeviceOut(
            id=row.id,
            user_id=row.user_id,
            platform=row.platform,  # type: ignore[arg-type]
            device_id=row.device_id,
            token=row.token,
            timezone=row.timezone,
            app_channel=row.app_channel,
            app_version=row.app_version,
            is_active=bool(row.is_active),
            created_at=row.created_at,
            updated_at=row.updated_at,
        ),
    )


@router.delete("/devices/{device_id}", response_model=PushDeviceDeleteOut)
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PushDeviceDeleteOut:
    found = deactivate_user_device(db, user_id=user.id, device_id=device_id)
    if found:
        log_action(
            db,
            category="notifications",
            action="disable_token",
            actor_user_id=user.id,
            details={
                "device_id": device_id,
            },
        )
    return PushDeviceDeleteOut(ok=True, device_id=device_id)
