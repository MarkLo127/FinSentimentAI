"""Password hashing + JWT issuing/parsing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:  # noqa: BLE001 — broken hash etc.
        return False


def create_access_token(*, sub: str) -> tuple[str, int]:
    """Returns (jwt_token, expires_in_seconds)."""
    s = get_settings()
    expires_seconds = s.access_token_expire_minutes * 60
    exp = datetime.now(UTC) + timedelta(seconds=expires_seconds)
    payload = {"sub": sub, "exp": exp, "iat": datetime.now(UTC)}
    token = jwt.encode(payload, s.secret_key, algorithm=s.algorithm)
    return token, expires_seconds


async def current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    cred_err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise cred_err
    s = get_settings()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
        username: str | None = payload.get("sub")
        if not username:
            raise cred_err
    except JWTError:
        raise cred_err from None

    user = (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None:
        raise cred_err
    return user
