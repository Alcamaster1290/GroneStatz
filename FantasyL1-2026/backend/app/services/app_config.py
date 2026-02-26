from __future__ import annotations

import re
from typing import Literal, cast

from sqlalchemy.orm import Session

from app.models import AppConfig

BadgeShape = Literal["circle", "rounded"]

PREMIUM_BADGE_ENABLED_KEY = "PREMIUM_BADGE_ENABLED"
PREMIUM_BADGE_TEXT_KEY = "PREMIUM_BADGE_TEXT"
PREMIUM_BADGE_COLOR_KEY = "PREMIUM_BADGE_COLOR"
PREMIUM_BADGE_SHAPE_KEY = "PREMIUM_BADGE_SHAPE"

PREMIUM_BADGE_DEFAULTS = {
    PREMIUM_BADGE_ENABLED_KEY: "true",
    PREMIUM_BADGE_TEXT_KEY: "P",
    PREMIUM_BADGE_COLOR_KEY: "#7C3AED",
    PREMIUM_BADGE_SHAPE_KEY: "circle",
}

PUBLIC_APP_CONFIG_KEYS = {
    PREMIUM_BADGE_ENABLED_KEY,
    PREMIUM_BADGE_TEXT_KEY,
    PREMIUM_BADGE_COLOR_KEY,
    PREMIUM_BADGE_SHAPE_KEY,
}

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _normalize_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_text(raw: str | None, default: str) -> str:
    if raw is None:
        return default
    value = raw.strip()
    if not value:
        return default
    return value[:2]


def _normalize_color(raw: str | None, default: str) -> str:
    if raw is None:
        return default
    value = raw.strip()
    if HEX_COLOR_RE.match(value):
        return value.upper()
    return default


def _normalize_shape(raw: str | None, default: BadgeShape) -> BadgeShape:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"circle", "rounded"}:
        return cast(BadgeShape, value)
    return default


def _load_keys(db: Session, keys: set[str]) -> dict[str, str]:
    rows = (
        db.query(AppConfig)
        .filter(AppConfig.key.in_(keys))
        .all()
    )
    return {row.key: row.value for row in rows}


def get_premium_badge_config(db: Session) -> dict[str, str | bool]:
    raw = _load_keys(db, PUBLIC_APP_CONFIG_KEYS)
    enabled_default = PREMIUM_BADGE_DEFAULTS[PREMIUM_BADGE_ENABLED_KEY] == "true"
    return {
        "enabled": _normalize_bool(raw.get(PREMIUM_BADGE_ENABLED_KEY), enabled_default),
        "text": _normalize_text(
            raw.get(PREMIUM_BADGE_TEXT_KEY),
            PREMIUM_BADGE_DEFAULTS[PREMIUM_BADGE_TEXT_KEY],
        ),
        "color": _normalize_color(
            raw.get(PREMIUM_BADGE_COLOR_KEY),
            PREMIUM_BADGE_DEFAULTS[PREMIUM_BADGE_COLOR_KEY],
        ),
        "shape": _normalize_shape(
            raw.get(PREMIUM_BADGE_SHAPE_KEY),
            cast(BadgeShape, PREMIUM_BADGE_DEFAULTS[PREMIUM_BADGE_SHAPE_KEY]),
        ),
    }


def get_public_app_config(db: Session) -> dict:
    return {
        "premium_badge": get_premium_badge_config(db),
    }


def update_premium_badge_config(
    db: Session,
    *,
    enabled: bool,
    text: str,
    color: str,
    shape: BadgeShape,
) -> dict[str, str | bool]:
    clean_text = _normalize_text(text, PREMIUM_BADGE_DEFAULTS[PREMIUM_BADGE_TEXT_KEY])
    clean_color = _normalize_color(color, PREMIUM_BADGE_DEFAULTS[PREMIUM_BADGE_COLOR_KEY])
    clean_shape = _normalize_shape(shape, "circle")

    values = {
        PREMIUM_BADGE_ENABLED_KEY: "true" if enabled else "false",
        PREMIUM_BADGE_TEXT_KEY: clean_text,
        PREMIUM_BADGE_COLOR_KEY: clean_color,
        PREMIUM_BADGE_SHAPE_KEY: clean_shape,
    }

    for key, value in values.items():
        row = db.get(AppConfig, key)
        if row:
            row.value = value
        else:
            db.add(AppConfig(key=key, value=value))

    db.commit()
    return get_premium_badge_config(db)
