# Railway Deployment Guide

This guide walks through deploying FinSentimentAI to [Railway](https://railway.com).
The repo ships with three `railway.json` config files that pin each service's
build + deploy spec; what's below covers the **one-time dashboard wiring**
(GitHub link, env vars, public domains) that Railway stores server-side.

---

## 1. Prerequisites

- Railway account on **Hobby** or **Pro** plan (Free plan can't deploy past Railway's build backlog throttle).
- GitHub repo `MarkLo127/FinSentimentAI` pushed (master branch).
- API keys ready:
  - `ANTHROPIC_API_KEY` — https://console.anthropic.com/
  - `MARKETAUX_API_KEY` — https://www.marketaux.com/
  - `FINNHUB_API_KEY` — https://finnhub.io/
  - `NEWSAPI_KEY` — https://newsapi.org/
  - `ALPHA_VANTAGE_KEY` — https://www.alphavantage.co/
  - `JINA_API_KEY` (optional, raises Reader rate limit) — https://jina.ai/

---

## 2. Services overview

The stack runs as **4 Railway services**:

| Service     | Source                  | Root Dir   | Railway Config Path       | Public Domain |
|-------------|-------------------------|------------|---------------------------|---------------|
| `postgres`  | Railway template        | —          | —                         | No            |
| `backend`   | GitHub repo (Dockerfile)| `backend`  | `railway.json` (default)  | No (private)  |
| `scheduler` | GitHub repo (Dockerfile)| `backend`  | `railway.scheduler.json`  | No            |
| `frontend`  | GitHub repo (Dockerfile)| `frontend` | `railway.json` (default)  | **Yes**       |

`backend` and `scheduler` share the same `backend/Dockerfile` — the scheduler's
`railway.scheduler.json` overrides `startCommand` so the same image runs as an
APScheduler worker instead of uvicorn.

---

## 3. Step-by-step setup

### 3.1 Create the project

1. Railway dashboard → **New Project** → **Deploy from GitHub repo** → pick `MarkLo127/FinSentimentAI`.
2. Railway will offer to create the first service automatically — cancel it; we'll add each service explicitly below so root directories and config paths are correct.

### 3.2 Add Postgres

1. `+ New` → **Database** → **Add PostgreSQL**.
2. Wait until status is **Active**. Railway auto-creates a `DATABASE_URL` variable on this service that other services reference via `${{Postgres.DATABASE_URL}}`.

### 3.3 Add `backend`

1. `+ New` → **GitHub Repo** → select `FinSentimentAI`.
2. Service **Settings**:
   - **Root Directory**: `backend`
   - **Railway Config File**: leave as `railway.json` (default).
   - **Networking** → leave **Public Networking** disabled (frontend reaches it over the private network).
3. **Variables** tab — paste:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ANTHROPIC_API_KEY=...
   ANTHROPIC_MODEL=claude-haiku-4-5
   MARKETAUX_API_KEY=...
   FINNHUB_API_KEY=...
   NEWSAPI_KEY=...
   ALPHA_VANTAGE_KEY=...
   JINA_API_KEY=...
   SECRET_KEY=<long random string, e.g. `openssl rand -hex 32`>
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=1440
   MONITORED_TICKERS=TSM
   NEWS_FETCH_INTERVAL_MINUTES=30
   RUN_MIGRATIONS=1
   SEED_ON_START=0
   CORS_ORIGINS=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
   LOG_LEVEL=INFO
   ```
4. Deploy. Watch the log for `[entrypoint] running alembic upgrade head` followed by `Uvicorn running on http://0.0.0.0:<PORT>`.

### 3.4 Add `scheduler`

1. `+ New` → **GitHub Repo** → select the same repo.
2. Service **Settings**:
   - **Root Directory**: `backend`
   - **Railway Config File**: `railway.scheduler.json` ← important
3. **Variables** — copy the same block as `backend`, but change:
   ```
   RUN_MIGRATIONS=0
   ```
   (only `backend` runs alembic; this avoids the two services racing on the `alembic_version` row.)
4. Deploy. Log should show `[entrypoint] skipping migrations (RUN_MIGRATIONS=0)` then APScheduler boot messages.

### 3.5 Add `frontend`

1. `+ New` → **GitHub Repo** → select the same repo.
2. Service **Settings**:
   - **Root Directory**: `frontend`
   - **Railway Config File**: `railway.json` (default)
   - **Networking** → **Generate Domain** (this is the user-facing URL).
3. **Variables**:
   ```
   BACKEND_HOST=${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}
   ```
   `PORT` is auto-injected by Railway — nginx's template uses it for `listen`.
4. Deploy. nginx will template the conf with `BACKEND_HOST` on container start.

### 3.6 Final pass

After the frontend's public domain is assigned, go back to **`backend` → Variables** and confirm `CORS_ORIGINS` evaluates to the actual domain (Railway resolves the `${{frontend.RAILWAY_PUBLIC_DOMAIN}}` reference automatically). Re-deploy backend if you edited the value.

---

## 4. Verification checklist

1. **Postgres** — service status is `Active`; backend's `DATABASE_URL` resolves on first connection.
2. **Backend** — runtime log shows `Uvicorn running on http://0.0.0.0:<PORT>`. Temporarily generate a public domain and hit `/api/health` → expect `{"status":"ok","service":"finsentiment-ai"}`. Revoke the public domain afterwards.
3. **Scheduler** — log shows `skipping migrations` + APScheduler job registrations (news fetch, sentiment analysis, daily summary).
4. **Frontend** — `https://<frontend-domain>/` loads the SPA. Open browser DevTools → Network: requests to `/api/...` return 200 (proves the nginx `BACKEND_HOST` proxy is hitting backend over the Railway private network).
5. **End-to-end** — register a user, add a stock ticker, trigger a manual refresh; news + sentiment should appear within ~60 s.

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Frontend returns 502 on `/api/*` | `BACKEND_HOST` wrong | Must be `host:port`. Use `${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}` — both refs required. |
| Backend boot loops at `alembic upgrade head` | Both backend + scheduler trying to migrate | Scheduler must have `RUN_MIGRATIONS=0`. |
| CORS errors in browser | `CORS_ORIGINS` doesn't match the actual frontend domain | Set `CORS_ORIGINS=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}` and re-deploy backend. |
| `Deploys have been paused temporarily` banner | Railway platform incident (often throttles Hobby plans during backlog) | Check https://status.railway.com/ — wait or temporarily upgrade to Pro. |
| Backend can't reach Postgres | Using wrong DB URL | Must be `${{Postgres.DATABASE_URL}}` (`backend/database.py` auto-rewrites `postgres://` → `postgresql+asyncpg://`). |
| Scheduler dies on boot with `Address already in use` | You set a port for it | Scheduler is a worker, not an HTTP server — remove any `PORT` override and don't generate a domain. |
