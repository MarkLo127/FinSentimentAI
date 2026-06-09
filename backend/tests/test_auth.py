"""Auth endpoint tests — Google sign-in flow.

Google ID-token verification is mocked: we patch
``google.oauth2.id_token.verify_oauth2_token`` so tests don't need a real
Google credential. The router code path (lookup-or-create user + issue JWT)
is what we actually exercise."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")

import database  # noqa: E402
from config import get_settings  # noqa: E402
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    # Pick up the env GOOGLE_CLIENT_ID we set above.
    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    from sqlalchemy import JSON

    from models.comment import Comment
    from models.market_summary import MarketSummary
    from models.sentiment import SentimentResult

    Comment.__table__.c.platform_metadata.type = JSON()
    SentimentResult.__table__.c.analysis_metadata.type = JSON()
    MarketSummary.__table__.c.top_keywords.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_db_override():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


def _idinfo(sub: str, email: str, name: str = "Test User") -> dict:
    """A minimal valid Google ID-token payload."""
    return {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": name,
        "aud": "test-google-client-id",
        "iss": "https://accounts.google.com",
    }


@pytest.mark.asyncio
async def test_google_first_login_creates_user_and_me_works(client: AsyncClient):
    info = _idinfo("google-sub-001", "alice@example.com", "Alice")
    with patch(
        "routers.auth.google_id_token.verify_oauth2_token", return_value=info
    ):
        r = await client.post("/api/auth/google", json={"credential": "fake-id-token"})
    assert r.status_code == 200, r.text
    body = r.json()
    token = body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0

    r = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"] == "alice@example.com"
    # username is derived from the email local part
    assert me["username"].startswith("alice")


@pytest.mark.asyncio
async def test_google_second_login_returns_same_user(client: AsyncClient):
    info = _idinfo("google-sub-002", "bob@example.com")
    with patch(
        "routers.auth.google_id_token.verify_oauth2_token", return_value=info
    ):
        r1 = await client.post("/api/auth/google", json={"credential": "tok1"})
        r2 = await client.post("/api/auth/google", json={"credential": "tok2"})
    assert r1.status_code == 200 and r2.status_code == 200

    headers1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}
    headers2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    me1 = (await client.get("/api/users/me", headers=headers1)).json()
    me2 = (await client.get("/api/users/me", headers=headers2)).json()
    assert me1["id"] == me2["id"], "second login must reuse the same DB row"


@pytest.mark.asyncio
async def test_google_invalid_credential_returns_401(client: AsyncClient):
    with patch(
        "routers.auth.google_id_token.verify_oauth2_token",
        side_effect=ValueError("invalid token"),
    ):
        r = await client.post("/api/auth/google", json={"credential": "garbage"})
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_google_unverified_email_returns_401(client: AsyncClient):
    info = _idinfo("google-sub-003", "evil@example.com")
    info["email_verified"] = False
    with patch(
        "routers.auth.google_id_token.verify_oauth2_token", return_value=info
    ):
        r = await client.post("/api/auth/google", json={"credential": "tok"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient):
    r = await client.get("/api/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_with_garbage_token_returns_401(client: AsyncClient):
    r = await client.get(
        "/api/users/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert r.status_code == 401
