# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FinSentiment AI: news-driven sentiment dashboard for US + Taiwan equities. The defining product idea is "anti-clickbait" — sentiment is computed from **full article body**, not headline, by **Claude Haiku 4.5** with bilingual (zh-TW + en) structured output. Replaces the original FinBERT + Chinese-RoBERTa plan with one LLM.

## Common commands

```bash
# Full stack (Postgres + pgAdmin + backend + scheduler + nginx frontend)
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

# One-shot manual ops (all idempotent)
cd backend && uv run python -m scripts.run_pipeline TSM         # fetch+extract+persist one ticker
cd backend && uv run python -m scripts.backfill_sentiment       # run Claude over un-analyzed rows
cd backend && uv run python -m scripts.run_daily_summary        # recompute today's market_summary
cd backend && uv run python -m scripts.run_scheduler            # foreground APScheduler (what the scheduler container runs)
cd backend && uv run python -m scripts.seed_stocks              # 10-stock starter seed (off by default)
```

## Architecture (the parts that span multiple files)

**Three runtime processes**, all sharing one Postgres:

1. `backend` — FastAPI + SQLAlchemy 2.0 async. On startup ([backend/main.py](backend/main.py)) it (a) overlays UI-managed settings from `app_settings` table into `os.environ`, (b) reaps stale `running` refresh jobs. Migrations run from the entrypoint when `RUN_MIGRATIONS=1` (backend only; scheduler is `0` to avoid racing).
2. `scheduler` — separate container running [backend/services/scheduler.py](backend/services/scheduler.py). Three APScheduler jobs, all idempotent: `pipeline_cycle` (30 min) → `sentiment_cycle` (10 min) → `daily_summary` (23:00 UTC). Restart-safe: a crash mid-cycle just leaves work for the next tick.
3. `frontend` — nginx-served Vite SPA proxying `/api` → backend.

**Two-stage data flow** — pipeline persists raw rows; sentiment is computed by a *separate* job. Do not collapse these into one stage:

- **Pipeline** ([backend/services/pipeline.py](backend/services/pipeline.py)) fans out to 6 fetchers in [backend/services/fetchers/](backend/services/fetchers/) (Marketaux, Finnhub, NewsAPI, AlphaVantage, StockTwits, PTT) in parallel. For news URLs it runs the **3-layer fallback extractor** ([backend/services/content_extractor.py](backend/services/content_extractor.py)): Jina Reader → trafilatura → API-provided snippet, recording which layer won in `news.fetched_via`. Dedupe is by `url_hash` with `ON CONFLICT DO NOTHING` to survive concurrent scheduler/refresh ticks. Alpha Vantage rows that carry a baseline sentiment label get an additional `sentiment_results` row tagged `model_version='alpha_vantage_v1'` — used by `scripts/compare_baselines.py` as ground-truth comparison.
- **Sentiment** ([backend/services/sentiment_analyzer.py](backend/services/sentiment_analyzer.py)) is invoked by [backend/scripts/backfill_sentiment.py](backend/scripts/backfill_sentiment.py) with concurrency=5 over rows that don't yet have a `model_version='claude-haiku-4-5'` row. The system prompt is **deliberately > 4096 tokens** to meet Haiku 4.5's prompt-cache minimum; the marker is placed via `cache_control={"type": "ephemeral"}` on the system block. Output is the `SentimentAnalysis` pydantic model — 9 fields including bilingual `title_zh`/`title_en`, `key_drivers_zh`/`key_drivers_en`, `reasoning_zh`/`reasoning_en`, plus `is_clickbait` (the 標題殺人 detector). When editing the prompt, **do not drop below 4096 tokens** or the cache discount disappears.

**Three triggers for the same pipeline + sentiment work** — they share code paths and dedupe naturally:
- Scheduler tick → `pipeline_cycle` / `sentiment_cycle`
- `POST /api/stocks/{symbol}/refresh` → detached `asyncio.create_task` in [backend/services/refresh_runner.py](backend/services/refresh_runner.py) (capped by `Semaphore(2)`), tracked in `refresh_jobs` table, browser polls `/api/refresh-jobs/{id}`
- Manual CLI: `uv run python -m scripts.run_pipeline TSM`

**Watchlist is DB-driven, not env-driven.** `scheduler._active_tickers()` reads the `stocks` table — `MONITORED_TICKERS` in env is legacy. Users manage the watchlist via the dashboard's "+ 新增" UI. `SEED_ON_START=0` by default for this reason; flip to `1` only for the 10-stock starter.

**Settings overlay system.** Operator-editable API keys (Anthropic + 4 news + Jina) can be set via `PUT /api/admin/settings` and stored in the `app_settings` table. [backend/services/settings_store.py](backend/services/settings_store.py) `overlay_db_into_env()` is called on backend lifespan startup, after each admin write, AND at the top of every scheduler tick — it mutates `os.environ` and clears the `get_settings` + `get_analyzer` `lru_cache`s so subsequent reads see new values. Only keys in `ALLOWED_KEYS` are honored. Env-set values take precedence is **not** correct here: the DB overlay wins because it's written into `os.environ` directly.

**Async DB URL normalization** in [backend/database.py](backend/database.py) rewrites `postgres://` / `postgresql://` → `postgresql+asyncpg://` so Railway/Heroku/Supabase-style URLs work without manual edits.

## Conventions worth knowing

- Python 3.12, `uv` for env+deps (`uv sync`, `uv run …`). Don't use pip directly.
- Ruff target `py312`, line length 100.
- All DB code is async SQLAlchemy 2.0 with `AsyncSession`; never block on sync sessions inside async paths.
- New tables → add to [backend/models/](backend/models/), generate Alembic revision, **manually inspect** the autogen output (it sometimes misses index/constraint nuances).
- Logging is `loguru`; use `logger.info("msg {}", value)` (brace placeholder), not f-strings.
- Frontend uses React Query for all server state; don't add a second cache layer. Auth token lives in `localStorage` under `TOKEN_KEY = 'finsentiment.token'` and is attached by an axios interceptor in [frontend/src/services/api.ts](frontend/src/services/api.ts).

## API surface

Routes are mounted in [backend/main.py](backend/main.py); each module lives under [backend/routers/](backend/routers/). Auth uses JWT (`Bearer`) via [backend/services/auth.py](backend/services/auth.py); `/api/admin/*` and `/api/refresh-jobs/*` require login. See README.md for the endpoint table.
