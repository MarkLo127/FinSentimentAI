"""Operator-facing settings management.

⚠️ This router is intentionally UN-AUTHENTICATED. The deployment model is
single-user local dev (Docker on the operator's machine). If you ever expose
this beyond localhost, put it behind the JWT-protected ``current_user``
dependency.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

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
async def get_settings_status() -> list[dict]:
    return await list_settings_status()


@router.put("/settings/{key}", response_model=SettingStatus)
async def put_setting(key: str, payload: SettingUpdate) -> dict:
    key = key.upper()
    if key not in ALLOWED_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown key: {key}")
    try:
        await set_setting(key, payload.value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    # Return the new status row
    all_status = await list_settings_status()
    for row in all_status:
        if row["key"] == key:
            return row
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "row missing after upsert")


@router.delete("/settings/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting_endpoint(key: str) -> None:
    key = key.upper()
    if key not in ALLOWED_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown key: {key}")
    await delete_setting(key)
