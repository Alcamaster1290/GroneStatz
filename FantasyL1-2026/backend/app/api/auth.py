from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models import PasswordResetToken, User
from app.schemas.auth import PasswordResetConfirm, PasswordResetOut, PasswordResetRequest, Token, UserCreate
from app.services.rate_limit import rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])

AUTH_RATE_LIMIT_WINDOW = 60
AUTH_RATE_LIMIT_MAX = 12
RESET_TOKEN_TTL_MINUTES = 20


def _get_client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"auth:{ip}"


def _enforce_rate_limit(request: Request) -> None:
    key = _get_client_key(request)
    allowed = rate_limiter.allow(key, AUTH_RATE_LIMIT_MAX, AUTH_RATE_LIMIT_WINDOW)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limited")


@router.post("/register", response_model=Token)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> Token:
    _enforce_rate_limit(request)
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email_already_registered")

    user = User(email=payload.email, password_hash=get_password_hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> Token:
    _enforce_rate_limit(request)
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return Token(access_token=token)


@router.post("/reset/request", response_model=PasswordResetOut)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetOut:
    _enforce_rate_limit(request)
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user:
        return PasswordResetOut(ok=True)

    code = f"{secrets.randbelow(1000000):06d}"
    token_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)

    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    db.commit()

    settings = get_settings()
    if settings.APP_ENV != "prod":
        logging.info(f"Password reset code for {user.email}: {code}")

    return PasswordResetOut(ok=True)


@router.post("/reset/confirm", response_model=PasswordResetOut)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetOut:
    _enforce_rate_limit(request)
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reset_code_invalid")

    token_hash = hashlib.sha256(payload.code.strip().encode("utf-8")).hexdigest()
    token = (
        db.execute(
            select(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
            )
            .order_by(PasswordResetToken.created_at.desc())
        )
        .scalars()
        .first()
    )
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reset_code_invalid")
    if token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reset_code_expired")

    user.password_hash = get_password_hash(payload.new_password)
    token.used_at = datetime.now(timezone.utc)
    db.commit()

    return PasswordResetOut(ok=True)
