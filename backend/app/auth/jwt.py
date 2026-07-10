import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import RefreshToken, User

settings = get_settings()

ALGORITHM = "RS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_private_key, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


async def store_refresh_token(db: AsyncSession, user_id: int, token: str) -> RefreshToken:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    row = RefreshToken(user_id=user_id, token_hash=_hash_token(token), expires_at=expires_at)
    db.add(row)
    await db.flush()
    return row


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_public_key, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        return None


async def rotate_refresh_token(db: AsyncSession, refresh_token: str) -> tuple[str, str, User] | None:
    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None

    user_result = await db.execute(select(User).where(User.id == row.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return None

    row.revoked_at = datetime.now(timezone.utc)
    new_refresh = create_refresh_token()
    await store_refresh_token(db, user.id, new_refresh)
    access = create_access_token(user.id)
    return access, new_refresh, user


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> None:
    token_hash = _hash_token(refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one_or_none()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
