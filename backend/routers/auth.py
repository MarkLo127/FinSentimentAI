from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.user import User
from schemas.user import GoogleAuthRequest, Token, UserPublic
from services.auth import create_access_token, current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


_USERNAME_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


async def _unique_username(db: AsyncSession, email: str) -> str:
    """Derive a URL-safe username from the Google email's local part,
    suffixing -N if needed to dodge collisions with prior users."""
    base = _USERNAME_SAFE.sub("-", email.split("@", 1)[0]).strip("-") or "user"
    base = base[:40]  # leave room for a "-NNN" suffix under the 50-char limit
    candidate = base
    i = 1
    while True:
        exists = (
            await db.execute(select(User.id).where(User.username == candidate))
        ).scalar_one_or_none()
        if exists is None:
            return candidate
        i += 1
        candidate = f"{base}-{i}"


@router.post("/google", response_model=Token)
async def google_auth(
    payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)
) -> Token:
    """Exchange a Google Identity Services ID token for our app JWT.

    Flow: SPA pops the Google sign-in, receives a JWT ID token, POSTs it here.
    We verify the signature + audience against ``GOOGLE_CLIENT_ID``, look up
    or create the user keyed on the Google ``sub`` claim, then mint our own
    short-lived JWT.
    """
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is not configured for Google sign-in (GOOGLE_CLIENT_ID missing).",
        )

    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        logger.warning("Google ID token verification failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        ) from None

    google_sub = idinfo.get("sub")
    email = idinfo.get("email")
    email_verified = idinfo.get("email_verified", False)
    if not google_sub or not email or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential missing verified sub/email",
        )

    # Primary key: Google sub. Falls back to email so a user who previously
    # signed up some other way gets transparently linked on first Google login.
    user = (
        await db.execute(select(User).where(User.google_sub == google_sub))
    ).scalar_one_or_none()
    if user is None:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    if user is None:
        username = await _unique_username(db, email)
        user = User(
            username=username,
            email=email,
            google_sub=google_sub,
            password_hash=None,
        )
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Race with a concurrent first-login of the same Google account.
            user = (
                await db.execute(
                    select(User).where(User.google_sub == google_sub)
                )
            ).scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not create user",
                ) from None
        else:
            await db.refresh(user)
    elif user.google_sub != google_sub:
        # Existing email account → link the Google identity on first use.
        user.google_sub = google_sub
        await db.commit()

    token, expires_in = create_access_token(sub=user.username)
    return Token(access_token=token, expires_in=expires_in)


@users_router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(current_user)) -> User:
    return user
