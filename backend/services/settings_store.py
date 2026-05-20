"""Bridge between the ``app_settings`` table and the in-process
``Settings`` pydantic singleton.

Both the FastAPI backend (lifespan startup + after each /api/admin/settings
PUT) and the scheduler (at the top of every cycle) call
``overlay_db_into_env`` to pull any operator-set keys out of the DB into
``os.environ``, then clear the ``get_settings`` / ``get_analyzer``
lru_caches so subsequent reads see the new values.

Only a fixed list of keys is allowed in/out so a typo in the UI can't
leak arbitrary env vars into the process.
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from models.app_setting import AppSetting

# Keys the UI is allowed to set. Each maps to the env var the rest of the
# code already reads via pydantic-settings.
ALLOWED_KEYS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "MARKETAUX_API_KEY",
    "FINNHUB_API_KEY",
    "NEWSAPI_KEY",
    "ALPHA_VANTAGE_KEY",
    "JINA_API_KEY",
)


def _clear_settings_caches() -> None:
    """Drop the lru-cached `Settings` so the next get_settings() picks up
    the freshly-mutated os.environ. Same for the analyzer (it captures the
    Anthropic key into the client at construction)."""
    from config import get_settings

    get_settings.cache_clear()
    try:
        from services.sentiment_analyzer import get_analyzer

        get_analyzer.cache_clear()
    except Exception:  # noqa: BLE001 — sentiment_analyzer optional in some flows
        pass


async def _fetch_all(session: AsyncSession) -> dict[str, str]:
    rows = await session.execute(select(AppSetting.key, AppSetting.value))
    return {k: v for k, v in rows.all() if k in ALLOWED_KEYS and v}


async def overlay_db_into_env(*, session: AsyncSession | None = None) -> int:
    """Read app_settings, overwrite the matching os.environ entries, clear
    caches. Returns how many keys were applied."""
    if session is None:
        async with SessionLocal() as s:
            kvs = await _fetch_all(s)
    else:
        kvs = await _fetch_all(session)

    for k, v in kvs.items():
        os.environ[k] = v
    if kvs:
        _clear_settings_caches()
    return len(kvs)


async def list_settings_status() -> list[dict]:
    """For the UI: return one row per allowed key with whether it's set
    in DB and/or env. Never returns the value itself."""
    async with SessionLocal() as session:
        rows = await session.execute(select(AppSetting.key, AppSetting.updated_at))
        db_rows = {k: ts for k, ts in rows.all()}
    out: list[dict] = []
    for key in ALLOWED_KEYS:
        db_ts = db_rows.get(key)
        env_set = bool(os.environ.get(key))
        out.append(
            {
                "key": key,
                "set_in_db": key in db_rows,
                "set_in_env": env_set,
                "is_set": key in db_rows or env_set,
                "updated_at": db_ts.isoformat() if db_ts else None,
            }
        )
    return out


async def set_setting(key: str, value: str) -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"unknown setting key: {key!r}")
    if not value:
        raise ValueError("value cannot be empty — use DELETE to remove a key")
    async with SessionLocal() as session:
        stmt = (
            pg_insert(AppSetting)
            .values(key=key, value=value)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value},
            )
        )
        await session.execute(stmt)
        await session.commit()
    # Apply immediately so the same process picks it up
    os.environ[key] = value
    _clear_settings_caches()


async def delete_setting(key: str) -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"unknown setting key: {key!r}")
    async with SessionLocal() as session:
        row = (
            await session.execute(select(AppSetting).where(AppSetting.key == key))
        ).scalar_one_or_none()
        if row is not None:
            await session.delete(row)
            await session.commit()
    # Don't unset os.environ — the .env-loaded value remains the fallback
    _clear_settings_caches()
