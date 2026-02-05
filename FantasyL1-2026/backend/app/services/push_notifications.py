from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import PushDeviceToken, Round, RoundPushNotification
from app.schemas.notifications import PushDeviceRegisterIn

logger = logging.getLogger(__name__)

FCM_SCOPE = ["https://www.googleapis.com/auth/firebase.messaging"]
REMINDER_TYPE = "round_deadline"


@dataclass
class ReminderRunStats:
    dry_run: bool
    scanned_rounds: int = 0
    eligible_rounds: int = 0
    total_devices: int = 0
    candidates: int = 0
    sent: int = 0
    skipped: int = 0
    errors: int = 0
    push_enabled: bool = False

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "dry_run": self.dry_run,
            "scanned_rounds": self.scanned_rounds,
            "eligible_rounds": self.eligible_rounds,
            "total_devices": self.total_devices,
            "candidates": self.candidates,
            "sent": self.sent,
            "skipped": self.skipped,
            "errors": self.errors,
            "push_enabled": self.push_enabled,
        }


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def list_user_devices(db: Session, user_id: int) -> list[PushDeviceToken]:
    return (
        db.execute(
            select(PushDeviceToken)
            .where(PushDeviceToken.user_id == user_id)
            .order_by(PushDeviceToken.updated_at.desc())
        )
        .scalars()
        .all()
    )


def register_user_device(
    db: Session,
    *,
    user_id: int,
    payload: PushDeviceRegisterIn,
) -> PushDeviceToken:
    row = db.execute(
        select(PushDeviceToken).where(
            PushDeviceToken.user_id == user_id,
            PushDeviceToken.device_id == payload.device_id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PushDeviceToken(
            user_id=user_id,
            platform=payload.platform,
            device_id=payload.device_id,
            token=payload.token,
            timezone=payload.timezone,
            app_channel=payload.app_channel,
            app_version=payload.app_version,
            is_active=True,
        )
        db.add(row)
    else:
        row.platform = payload.platform
        row.token = payload.token
        row.timezone = payload.timezone
        row.app_channel = payload.app_channel
        row.app_version = payload.app_version
        row.is_active = True
        row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)
    logger.info(
        "notifications:register_token user_id=%s device_id=%s platform=%s active=%s",
        user_id,
        payload.device_id,
        payload.platform,
        True,
    )
    return row


def deactivate_user_device(db: Session, *, user_id: int, device_id: str) -> bool:
    row = db.execute(
        select(PushDeviceToken).where(
            PushDeviceToken.user_id == user_id,
            PushDeviceToken.device_id == device_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.is_active = False
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


class FCMClient:
    def __init__(self, settings: Settings):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        project_id = (settings.FCM_PROJECT_ID or "").strip()
        if not project_id:
            raise ValueError("fcm_project_id_missing")
        self._project_id = project_id
        creds = self._load_credentials(settings, service_account)
        if creds is None:
            raise ValueError("fcm_credentials_missing")
        self._session = AuthorizedSession(creds)

    @staticmethod
    def _load_credentials(settings: Settings, service_account_module):
        raw_json = (settings.FCM_SERVICE_ACCOUNT_JSON or "").strip()
        file_hint = (settings.GOOGLE_APPLICATION_CREDENTIALS or "").strip()

        if raw_json:
            if raw_json.startswith("{"):
                info = json.loads(raw_json)
                return service_account_module.Credentials.from_service_account_info(
                    info,
                    scopes=FCM_SCOPE,
                )
            json_path = Path(raw_json)
            if json_path.exists():
                return service_account_module.Credentials.from_service_account_file(
                    str(json_path),
                    scopes=FCM_SCOPE,
                )
        if file_hint:
            creds_path = Path(file_hint)
            if creds_path.exists():
                return service_account_module.Credentials.from_service_account_file(
                    str(creds_path),
                    scopes=FCM_SCOPE,
                )
        return None

    def send_round_deadline_message(
        self,
        *,
        token: str,
        round_number: int,
        ends_at: datetime,
        hours_before: int,
    ) -> Tuple[bool, str | None, bool]:
        ends_utc = _to_utc(ends_at)
        url = (
            f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"
        )
        body = {
            "message": {
                "token": token,
                "notification": {
                    "title": f"Ronda {round_number}: cierre cercano",
                    "body": (
                        f"Tu ronda cierra en {hours_before} horas "
                        f"({ends_utc.strftime('%d/%m %H:%M UTC')})."
                    ),
                },
                "data": {
                    "type": REMINDER_TYPE,
                    "round_number": str(round_number),
                    "ends_at": ends_utc.isoformat(),
                },
            }
        }
        response = self._session.post(url, json=body, timeout=15)
        if 200 <= response.status_code < 300:
            return True, None, False

        text = response.text
        invalid_token = any(
            marker in text
            for marker in (
                "UNREGISTERED",
                "registration-token-not-registered",
                "INVALID_ARGUMENT",
            )
        )
        return False, f"fcm_error_{response.status_code}:{text[:500]}", invalid_token


def _build_fcm_client(settings: Settings) -> FCMClient | None:
    try:
        return FCMClient(settings)
    except Exception as exc:  # pragma: no cover - startup/runtime guard
        logger.warning("fcm_client_unavailable: %s", exc)
        return None


def run_round_deadline_reminders(
    db: Session,
    *,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> dict[str, int | bool]:
    settings = settings or get_settings()
    stats = ReminderRunStats(dry_run=dry_run, push_enabled=bool(settings.PUSH_ENABLED))
    now = datetime.now(timezone.utc)
    reminder_delta = timedelta(hours=max(1, int(settings.PUSH_REMINDER_HOURS_BEFORE)))

    rounds = (
        db.execute(
            select(Round)
            .where(Round.is_closed.is_(False), Round.ends_at.is_not(None))
            .order_by(Round.round_number)
        )
        .scalars()
        .all()
    )
    stats.scanned_rounds = len(rounds)
    eligible_rounds = []
    for round_obj in rounds:
        if round_obj.ends_at is None:
            continue
        ends_at = _to_utc(round_obj.ends_at)
        if now >= ends_at:
            continue
        if now >= (ends_at - reminder_delta):
            eligible_rounds.append(round_obj)
    stats.eligible_rounds = len(eligible_rounds)
    if not eligible_rounds:
        return stats.as_dict()

    devices = (
        db.execute(select(PushDeviceToken).where(PushDeviceToken.is_active.is_(True)))
        .scalars()
        .all()
    )
    stats.total_devices = len(devices)
    if not devices:
        return stats.as_dict()

    fcm_client = None
    if settings.PUSH_ENABLED and not dry_run:
        fcm_client = _build_fcm_client(settings)

    for round_obj in eligible_rounds:
        for device in devices:
            stats.candidates += 1
            if not dry_run and not settings.PUSH_ENABLED:
                stats.skipped += 1
                continue
            existing = db.execute(
                select(RoundPushNotification.id).where(
                    RoundPushNotification.round_id == round_obj.id,
                    RoundPushNotification.device_token_id == device.id,
                    RoundPushNotification.notification_type == REMINDER_TYPE,
                )
            ).scalar_one_or_none()
            if existing:
                stats.skipped += 1
                continue

            if dry_run:
                continue

            row = RoundPushNotification(
                round_id=round_obj.id,
                device_token_id=device.id,
                notification_type=REMINDER_TYPE,
                status="pending",
            )
            db.add(row)
            db.flush()

            if fcm_client is None:
                row.status = "error"
                row.error = "fcm_client_unavailable"
                db.commit()
                stats.errors += 1
                continue

            ok, error_detail, invalid_token = fcm_client.send_round_deadline_message(
                token=device.token,
                round_number=round_obj.round_number,
                ends_at=round_obj.ends_at or now,
                hours_before=int(settings.PUSH_REMINDER_HOURS_BEFORE),
            )
            if ok:
                row.status = "sent"
                row.sent_at = datetime.now(timezone.utc)
                row.error = None
                stats.sent += 1
                logger.info(
                    "notifications:send_success round_number=%s device_id=%s",
                    round_obj.round_number,
                    device.device_id,
                )
            else:
                row.status = "error"
                row.error = error_detail
                stats.errors += 1
                logger.error(
                    "notifications:send_error round_number=%s device_id=%s error=%s",
                    round_obj.round_number,
                    device.device_id,
                    error_detail,
                )
                if invalid_token:
                    device.is_active = False
                    device.updated_at = datetime.now(timezone.utc)
            db.commit()

    return stats.as_dict()
