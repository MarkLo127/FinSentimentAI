"""Per-user API-key store backed by the ``app_settings`` table.

Each user pastes their own keys through the /settings UI; values are stored
Fernet-encrypted (see services/crypto.py) under a composite (user_id, key) PK.
At pipeline time we load a user's keys via ``get_user_keys`` and thread them
explicitly through the fetchers / analyzer — there is deliberately NO fallback
to the operator's env keys, so one user can never spend another's (or the
operator's) quota.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models.app_setting import AppSetting
from services.crypto import decrypt, encrypt

# Keys the UI is allowed to set, and the UserKeys attribute each maps to.
KEY_TO_FIELD: dict[str, str] = {
    "ANTHROPIC_API_KEY": "anthropic",
    "MARKETAUX_API_KEY": "marketaux",
    "FINNHUB_API_KEY": "finnhub",
    "NEWSAPI_KEY": "newsapi",
    "ALPHA_VANTAGE_KEY": "alpha_vantage",
    "JINA_API_KEY": "jina",
}
ALLOWED_KEYS: tuple[str, ...] = tuple(KEY_TO_FIELD)


@dataclass
class UserKeys:
    """A user's decrypted API keys. Missing keys are empty strings — callers
    must check before using (e.g. fetchers skip when their key is blank)."""

    anthropic: str = ""
    marketaux: str = ""
    finnhub: str = ""
    newsapi: str = ""
    alpha_vantage: str = ""
    jina: str = ""


async def _fetch_decrypted(session: AsyncSession, user_id: int) -> dict[str, str]:
    rows = await session.execute(
        select(AppSetting.key, AppSetting.value).where(AppSetting.user_id == user_id)
    )
    out: dict[str, str] = {}
    for key, enc in rows.all():
        if key not in ALLOWED_KEYS:
            continue
        plain = decrypt(enc)
        if plain:
            out[key] = plain
    return out


async def get_user_keys(
    user_id: int, *, session: AsyncSession | None = None
) -> UserKeys:
    if session is None:
        async with SessionLocal() as s:
            kv = await _fetch_decrypted(s, user_id)
    else:
        kv = await _fetch_decrypted(session, user_id)
    return UserKeys(**{KEY_TO_FIELD[k]: v for k, v in kv.items()})


async def list_settings_status(user_id: int) -> list[dict]:
    """For the UI: one row per allowed key with whether the user has set it.
    Never returns the value itself."""
    async with SessionLocal() as session:
        rows = await session.execute(
            select(AppSetting.key, AppSetting.updated_at).where(
                AppSetting.user_id == user_id
            )
        )
        db_rows = {k: ts for k, ts in rows.all()}
    out: list[dict] = []
    for key in ALLOWED_KEYS:
        db_ts = db_rows.get(key)
        out.append(
            {
                "key": key,
                "set_in_db": key in db_rows,
                "set_in_env": False,  # per-user model has no env fallback
                "is_set": key in db_rows,
                "updated_at": db_ts.isoformat() if db_ts else None,
            }
        )
    return out


async def set_setting(user_id: int, key: str, value: str) -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"unknown setting key: {key!r}")
    if not value:
        raise ValueError("value cannot be empty — use DELETE to remove a key")
    enc = encrypt(value)
    async with SessionLocal() as session:
        stmt = (
            pg_insert(AppSetting)
            .values(user_id=user_id, key=key, value=enc)
            .on_conflict_do_update(
                index_elements=["user_id", "key"],
                set_={"value": enc},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def delete_setting(user_id: int, key: str) -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"unknown setting key: {key!r}")
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.user_id == user_id, AppSetting.key == key
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            await session.delete(row)
            await session.commit()
