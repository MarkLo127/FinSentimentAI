<div align="center">

# 📈 FinSentiment AI

**News-driven financial sentiment dashboard**

Sentiment computed from the **full article body** — not the headline — by **Claude Haiku 4.5**.

**🌐 English · [繁體中文](README.md)**

</div>

---

<img src="screen_shot/1.png" width="49%" alt="Market overview" /> <img src="screen_shot/3.png" width="49%" alt="Stock detail" />

---

## What this is

FinSentiment AI is a news-driven sentiment dashboard for **US + Taiwan equities**. The defining product idea is **anti-clickbait**: sentiment is computed from the **full article body** — not the headline — by **Claude Haiku 4.5**, with bilingual (zh-TW + en) structured output. A single LLM replaces the original FinBERT + Chinese-RoBERTa plan, dropping the 2.4 GB torch dependency.

> The system is **fully multi-tenant / per-user isolated**: every user has their own watchlist, their own news/sentiment data, and their own encrypted API keys. There is **no background scheduler** — all analysis is **on-demand**, triggered by each user with their own keys.

## Screenshots

| Market overview | Stock trend + key drivers |
|---|---|
| ![dashboard](screen_shot/1.png) | ![stock](screen_shot/3.png) |
| **Watchlist + latest news** | **Per-article sentiment + full body** |
| ![watchlist](screen_shot/2.png) | ![news](screen_shot/5.png) |

**Per-user encrypted API key settings** — each user fills in their own, stored Fernet-encrypted:

![settings](screen_shot/7.png)

## Architecture

```
┌──────────┐    /api    ┌─────────────┐  asyncpg  ┌──────────────┐
│ Frontend │───────────▶│   Backend   │──────────▶│  PostgreSQL  │
│ React 19 │  (nginx    │   FastAPI   │           │     16       │
│  Vite 8  │   proxy)   └──────┬──────┘           │ (per-user)   │
└──────────┘                   │                  └──────────────┘
                               │ two-stage on-demand flow
              ┌────────────────┴─────────────────┐
              ▼                                   ▼
     ┌─────────────────┐                ┌───────────────────┐
     │  Pipeline       │   un-analyzed  │  Sentiment        │
     │  6 fetchers     │──── rows ─────▶│  Claude Haiku 4.5 │
     │  → 3-layer      │                │  + prompt cache    │
     │    extraction   │                │  bilingual output  │
     │  → dedupe       │                └───────────────────┘
     └─────────────────┘
```

**Two-stage data flow** (deliberately separated — do not collapse):

1. **Pipeline** (`run_for_ticker()`) fans out to 6 fetchers in parallel, each built with the **user's own key**. A 3-layer fallback extractor turns each URL into full Markdown; dedupe is by `(stock_id, url_hash)` with `ON CONFLICT DO NOTHING`.
2. **Sentiment** runs Claude over the user's **un-analyzed** rows, producing a 9-field bilingual structured result.

**Two triggers, one pipeline + sentiment (no scheduler):**
- `POST /api/stocks/{symbol}/refresh` → detached `asyncio` task (capped by `Semaphore(2)`), tracked in `refresh_jobs`, polled by the browser.
- Manual CLI: `uv run python -m scripts.run_pipeline <user_id> TSM`.

## 6 data sources (API-first, no scrapers)

| Type | Sources | Purpose |
|---|---|---|
| News | Marketaux · Finnhub · NewsAPI · Alpha Vantage | English financial news; AV ships its own sentiment score as a baseline |
| Social | PTT Stock board · StockTwits | Retail sentiment; StockTwits bullish/bearish flags as ground truth |
| Extraction | Jina Reader → trafilatura → snippet | 3-layer fallback to full body; winning layer recorded in `fetched_via` |

## AI design highlights

- **Claude Haiku 4.5** — one model for both Chinese and English, replacing a two-model FinBERT + RoBERTa stack.
- **Prompt caching** — the system prompt is deliberately **> 4096 tokens** to hit Haiku 4.5's cache minimum, saving ~90% on input cost from the 2nd article onward.
- **Bilingual structured output** — 9 fields per article: `label` / `confidence` / `is_clickbait` / `title_zh` / `title_en` / `key_drivers_zh` / `key_drivers_en` / `reasoning_zh` / `reasoning_en`.
- **Clickbait detection** — `is_clickbait` flags articles where the title contradicts the body's sentiment.
- **Measured cost** — backfilling 112 articles ≈ **$0.40**.

## Multi-tenancy & security

- **Per-user isolation is the central invariant.** `stocks` and `refresh_jobs` carry `user_id`; `news`/`comments`/`sentiment_results`/`market_summary` inherit it through the `stock_id` FK. `url_hash` uniqueness is **per-stock**, so the same public article can exist under two users' stocks with independent analysis.
- **Auth** — Google OAuth (`POST /api/auth/google`) issues a JWT; every route except `/api/auth/*` requires login and is scoped to `current_user`.
- **Per-user encrypted keys** — each user sets their own keys in `/settings`, stored **Fernet-encrypted** (key derived from `SECRET_KEY`). There is **no fallback to operator env keys** — no key, no fetch, so nobody spends anyone else's quota.

## Quick start

```bash
# 1. Set env vars (use a long random SECRET_KEY; users add API keys in /settings after login)
cp .env.example .env && $EDITOR .env

# 2. Start the full stack (postgres + pgAdmin + backend + nginx frontend — no scheduler)
docker compose up -d --build

# 3. Open the browser, sign in with Google, then add your own keys under Settings
open http://localhost:5173
```

| Service | URL | Credentials |
|---|---|---|
| Frontend (nginx + Vite SPA) | http://localhost:5173 | Google sign-in |
| Backend (FastAPI + OpenAPI) | http://localhost:8000/docs | — |
| pgAdmin | http://localhost:5050 | admin@local.dev / admin |
| Postgres | localhost:**5433** | finsentiment / finsentiment_dev |

> Port **5433** intentionally avoids the common host PostgreSQL 5432 conflict; in-container it's still 5432.

## Dev mode (without docker)

```bash
docker compose up -d postgres pgadmin                                  # Postgres still in a container
cd backend  && uv sync && uv run uvicorn main:app --reload --port 8000  # Backend hot-reload
cd frontend && bun install && bun run dev                              # Frontend hot-reload
```

## Manual CLI (data is per-user, so a user_id is required)

```bash
cd backend
uv run python -m scripts.run_pipeline <user_id> TSM   # fetch + extract + persist
uv run python -m scripts.backfill_sentiment           # run Claude over un-analyzed rows
uv run python -m scripts.run_daily_summary            # recompute today's market_summary
```

## API endpoints

All routes require login except `/api/auth/*`. Everything is scoped to `current_user`.

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/google` | Google OAuth → JWT |
| GET | `/api/users/me` | Current user (Bearer token) |
| GET | `/api/stocks` | User's watchlist |
| POST | `/api/stocks` | Add a stock to the watchlist |
| DELETE | `/api/stocks/{symbol}` | Remove a stock |
| GET | `/api/stocks/{symbol}?days=N` | Stock detail: trend + key drivers |
| GET | `/api/stocks/{symbol}/impact` | Per-article impact breakdown |
| POST | `/api/stocks/{symbol}/refresh` | Trigger an on-demand refresh job (202) |
| GET | `/api/market/today` | Today + yesterday + change |
| GET | `/api/market/history?days=N` | Time series |
| GET | `/api/market/trending?limit=N` | Leaderboard |
| GET | `/api/news?q=&symbol=&limit=N` | News list + sentiment snippet |
| GET | `/api/news/{id}` | Full body + analysis metadata |
| GET | `/api/news/{id}/translation/{lang}` | On-demand translation |
| GET / PUT / DELETE | `/api/admin/settings/{key}` | Manage per-user encrypted API keys |
| GET | `/api/refresh-jobs/{id}` | Poll a refresh job |
| GET | `/api/refresh-jobs` | List recent refresh jobs |

## Tests

```bash
cd backend  && uv run pytest                                   # 40 tests
cd frontend && bunx tsc --noEmit -p tsconfig.app.json          # type-check
cd frontend && bun run lint                                    # ESLint
```

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React 19 · Vite 8 · TypeScript 6 · Tailwind 3 · Recharts · React Router 7 · TanStack Query 5 · i18next (zh/en) · Google OAuth · Zod · lucide-react |
| Backend | FastAPI · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · asyncpg · httpx · tenacity · loguru · trafilatura · passlib · python-jose |
| AI | Anthropic SDK + Claude Haiku 4.5 (structured output + prompt caching) |
| Database | PostgreSQL 16 |
| Container | Docker Compose (postgres + pgAdmin + backend + frontend nginx) |
| Deploy | Railway |

## Conventions

- Python 3.12, `uv` for env + deps (`uv sync`, `uv run …`) — don't use pip directly.
- Ruff target `py312`, line length 100.
- All DB code is async SQLAlchemy 2.0 (`AsyncSession`) — never block on sync sessions in async paths.
- Logging via `loguru` with brace placeholders: `logger.info("msg {}", value)`.
- Frontend uses React Query for all server state; JWT lives in `localStorage` under `finsentiment.token`, attached by an axios interceptor.
- The sentiment system prompt is deliberately **> 4096 tokens** — do not drop it below the Haiku 4.5 cache minimum.
