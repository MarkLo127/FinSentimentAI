"""Auth endpoint tests using an in-memory SQLite + FastAPI TestClient."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-prod")

import database  # noqa: E402
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    # Patch JSONB columns for SQLite
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


@pytest.mark.asyncio
async def test_register_then_login_then_me(client: AsyncClient):
    payload = {"username": "alice", "email": "alice@example.com", "password": "supersecret1"}
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "alice"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body

    r = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "supersecret1"}
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert r.json()["token_type"] == "bearer"
    assert r.json()["expires_in"] > 0

    r = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "alice"


@pytest.mark.asyncio
async def test_register_rejects_duplicate(client: AsyncClient):
    p = {"username": "bob", "email": "bob@example.com", "password": "anothersecret"}
    assert (await client.post("/api/auth/register", json=p)).status_code == 201
    r = await client.post("/api/auth/register", json=p)
    assert r.status_code == 409

    # different email, same username — also rejected
    r = await client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob2@example.com", "password": "morestuff1"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_register_validates_input(client: AsyncClient):
    # password too short
    r = await client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "c@c.com", "password": "short"},
    )
    assert r.status_code == 422
    # bad username (space)
    r = await client.post(
        "/api/auth/register",
        json={"username": "no space", "email": "c@c.com", "password": "validpass1"},
    )
    assert r.status_code == 422
    # invalid email
    r = await client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "not-an-email", "password": "validpass1"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_with_wrong_password_fails(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"username": "dan", "email": "d@d.com", "password": "rightpass1"},
    )
    r = await client.post(
        "/api/auth/login", json={"username": "dan", "password": "wrongpass1"}
    )
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
