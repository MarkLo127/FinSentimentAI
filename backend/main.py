from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import get_settings
from routers import admin, auth, market, news, refresh_jobs, stocks
from services.refresh_runner import reap_stale_jobs

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FinSentiment backend starting")
    # API keys are now per-user + encrypted (loaded at refresh time), so there is
    # no global env overlay any more — each user's keys live in app_settings.
    try:
        reaped = await reap_stale_jobs()
        if reaped:
            logger.warning("reaped {} stale 'running' refresh job(s)", reaped)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reap_stale_jobs skipped: {}", exc)
    yield
    logger.info("FinSentiment backend stopping")


app = FastAPI(
    title="FinSentiment AI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stocks.router)
app.include_router(market.router)
app.include_router(news.router)
app.include_router(auth.router)
app.include_router(auth.users_router)
app.include_router(admin.router)
app.include_router(refresh_jobs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "finsentiment-ai"}
