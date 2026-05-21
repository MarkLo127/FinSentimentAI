"""Per-user API-key management.

Each authenticated user manages their OWN keys here — the endpoints are
scoped to ``current_user`` and operate on that user's encrypted rows in
``app_settings``. (Path prefix kept as /api/admin for frontend compatibility.)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from models.user import User
from services.auth import current_user
from services.settings_store import (
    ALLOWED_KEYS,
    delete_setting,
    list_settings_status,
    set_setting,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SettingStatus(BaseModel):
    key: str
    set_in_db: bool
    set_in_env: bool
    is_set: bool
    updated_at: str | None


class SettingUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=512)


@router.get("/settings", response_model=list[SettingStatus])
async def get_settings_status(
    user: Annotated[User, Depends(current_user)],
) -> list[dict]:
    return await list_settings_status(user.id)


@router.put("/settings/{key}", response_model=SettingStatus)
async def put_setting(
    key: str,
    payload: SettingUpdate,
    user: Annotated[User, Depends(current_user)],
) -> dict:
    key = key.upper()
    if key not in ALLOWED_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown key: {key}")
    try:
        await set_setting(user.id, key, payload.value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    all_status = await list_settings_status(user.id)
    for row in all_status:
        if row["key"] == key:
            return row
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "row missing after upsert")


@router.delete("/settings/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting_endpoint(
    key: str,
    user: Annotated[User, Depends(current_user)],
) -> None:
    key = key.upper()
    if key not in ALLOWED_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown key: {key}")
    await delete_setting(user.id, key)
