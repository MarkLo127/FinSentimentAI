# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FinSentiment AI: news-driven sentiment dashboard for US + Taiwan equities. The defining product idea is "anti-clickbait" — sentiment is computed from **full article body**, not headline, by **Claude Haiku 4.5** with bilingual (zh-TW + en) structured output. Replaces the original FinBERT + Chinese-RoBERTa plan with one LLM.

## Common commands

```bash
# Full stack (Postgres + pgAdmin + backend + nginx frontend)
# Analysis is fully on-demand — there is no scheduler container.
docker compose up -d --build
# Postgres is exposed on host port 5433 (not 5432) to avoid conflicts.

# Dev mode without docker — postgres still in container
docker compose up -d postgres pgadmin
cd backend  && uv sync && uv run uvicorn main:app --reload --port 8000
cd frontend && bun install && bun run dev

# Backend tests (52 tests)
cd backend && uv run pytest
cd backend && uv run pytest tests/test_pipeline.py::test_xxx -x   # single test

# Frontend type-check / lint
cd frontend && bunx tsc --noEmit -p tsconfig.app.json
cd frontend && bun run lint

# Alembic migrations (run from backend/)
cd backend && uv run alembic upgrade head
cd backend && uv run alembic revision --autogenerate -m "msg"

# One-shot manual ops (dev CLI; pipeline/backfill now take a user_id since data is per-user)
cd backend && uv run python -m scripts.run_pipeline <user_id> TSM   # fetch+extract+persist for one user's ticker
cd backend && uv run python -m scripts.backfill_sentiment           # run Claude over un-analyzed rows (env key)
cd backend && uv run python -m scripts.run_daily_summary            # recompute today's market_summary
```

## Architecture (the parts that span multiple files)

**Two runtime processes**, all sharing one Postgres:

1. `backend` — FastAPI + SQLAlchemy 2.0 async. On startup ([backend/main.py](backend/main.py)) it reaps stale `running` refresh jobs. Migrations run from the entrypoint when `RUN_MIGRATIONS=1`.
2. `frontend` — nginx-served Vite SPA proxying `/api` → backend.

**Multi-tenant / per-user isolation (the central invariant).** Every user has their own watchlist, their own news/sentiment/summaries, and their own API keys. The data tables that root this are `stocks` and `refresh_jobs` (both carry `user_id`); `news`/`comments`/`sentiment_results`/`market_summary` inherit isolation through their `stock_id` FK. `news.url_hash` / `comments.url_hash` are unique **per stock** (`uq_news_stock_url_hash`), not globally — the same public article can exist under two users' stocks with independent analysis. Every router filters by `current_user` (login is required on all routes except `/api/auth/*`).

**Two-stage data flow** — pipeline persists raw rows; sentiment is computed by a *separate* job. Do not collapse these into one stage:

- **Pipeline** ([backend/services/pipeline.py](backend/services/pipeline.py)) — `run_for_ticker(ticker, *, user_id, keys: UserKeys)` fans out to 6 fetchers in [backend/services/fetchers/](backend/services/fetchers/) (Marketaux, Finnhub, NewsAPI, AlphaVantage, StockTwits, PTT) in parallel, each constructed with the **user's own key**. The 3-layer fallback extractor ([backend/services/content_extractor.py](backend/services/content_extractor.py)) is Jina Reader → trafilatura → snippet, recording the winning layer in `news.fetched_via`. Dedupe is by `(stock_id, url_hash)` with `ON CONFLICT DO NOTHING`. Alpha Vantage baseline rows get a `model_version='alpha_vantage_v1'` `sentiment_results` row.
- **Sentiment** ([backend/services/sentiment_analyzer.py](backend/services/sentiment_analyzer.py)) — built per-request via `build_analyzer(user_key)` (not the global `get_analyzer()`), invoked by [backend/scripts/backfill_sentiment.py](backend/scripts/backfill_sentiment.py) `run(..., user_id=, anthropic_key=)` over the user's un-analyzed rows. The system prompt is **deliberately > 4096 tokens** to hit Haiku 4.5's prompt-cache minimum (marker via `cache_control={"type":"ephemeral"}`). Output is the `SentimentAnalysis` model with bilingual `title_*`/`key_drivers_*`/`reasoning_*` + `is_clickbait`. **Do not drop the prompt below 4096 tokens.**

**Two triggers for the same pipeline + sentiment work** (no scheduler — analysis is fully on-demand):
- `POST /api/stocks/{symbol}/refresh` → detached `asyncio.create_task` in [backend/services/refresh_runner.py](backend/services/refresh_runner.py) (capped by `Semaphore(2)`), tracked in `refresh_jobs`, browser polls `/api/refresh-jobs/{id}`. The runner loads the triggering user's keys and threads them through pipeline → backfill → daily_summary.
- Manual CLI: `uv run python -m scripts.run_pipeline <user_id> TSM`.

**Watchlist is per-user + DB-driven.** Each user manages their own list via the dashboard "+ 新增" UI; `(user_id, symbol)` is unique. `SEED_ON_START=0`.

**Per-user encrypted API keys.** Each user sets their own keys (Anthropic + 4 news + Jina) via `PUT /api/admin/settings` (auth-required, scoped to `current_user`). [backend/services/settings_store.py](backend/services/settings_store.py) stores them in `app_settings` under a composite `(user_id, key)` PK, **Fernet-encrypted** ([backend/services/crypto.py](backend/services/crypto.py), key derived from `SECRET_KEY`). Load them with `get_user_keys(user_id) -> UserKeys`. There is **no fallback to operator env keys** — a user with no key set simply can't fetch/analyze that source (so nobody spends anyone else's quota). Rotating `SECRET_KEY` invalidates all stored keys (users re-enter them).

**Async DB URL normalization** in [backend/database.py](backend/database.py) rewrites `postgres://` / `postgresql://` → `postgresql+asyncpg://` so Railway/Heroku/Supabase-style URLs work without manual edits.

## Conventions worth knowing

- Python 3.12, `uv` for env+deps (`uv sync`, `uv run …`). Don't use pip directly.
- Ruff target `py312`, line length 100.
- All DB code is async SQLAlchemy 2.0 with `AsyncSession`; never block on sync sessions inside async paths.
- New tables → add to [backend/models/](backend/models/), generate Alembic revision, **manually inspect** the autogen output (it sometimes misses index/constraint nuances).
- Logging is `loguru`; use `logger.info("msg {}", value)` (brace placeholder), not f-strings.
- Frontend uses React Query for all server state; don't add a second cache layer. Auth token lives in `localStorage` under `TOKEN_KEY = 'finsentiment.token'` and is attached by an axios interceptor in [frontend/src/services/api.ts](frontend/src/services/api.ts).

## API surface

Routes are mounted in [backend/main.py](backend/main.py); each module lives under [backend/routers/](backend/routers/). Auth uses JWT (`Bearer`) via [backend/services/auth.py](backend/services/auth.py). **Every route requires login except `/api/auth/*`** (register/login) — stocks, news, market, refresh-jobs, and admin/settings are all scoped to `current_user`. The frontend gates routes with `RequireAuth` ([frontend/src/components/RequireAuth.tsx](frontend/src/components/RequireAuth.tsx)) and bounces to `/login` on any 401. See README.md for the endpoint table.
