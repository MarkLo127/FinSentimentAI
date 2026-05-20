# FinSentiment AI

AI 金融市場情緒分析系統 — 透過 **Claude Haiku 4.5** 分析**完整新聞內文**（非標題），解決財經報導的「標題殺人」現象。


## 架構

```
┌──────────┐    /api    ┌─────────────┐  asyncpg  ┌──────────────┐
│ Frontend │───────────▶│   Backend   │──────────▶│  PostgreSQL  │
│ React 19 │   (nginx   │   FastAPI   │           │     16       │
│  Vite 8  │   proxy)   └──────┬──────┘           └──────────────┘
│  :5173   │                   │
└──────────┘                   │ Anthropic SDK
                               ▼
                       ┌───────────────────┐
                       │ Claude Haiku 4.5  │
                       │ + prompt cache    │
                       └───────────────────┘
                               ▲
┌──────────────────┐  every   │
│    Scheduler     │  30 min  │
│  APScheduler     │──────────┘
│ (separate svc)   │    pipeline → sentiment → daily_summary
└──────────────────┘
```

## 一鍵啟動

```bash
# 1. 填 API key（最少要 ANTHROPIC_API_KEY；4 個新聞 key 可空）
cp .env.example .env
$EDITOR .env

# 2. 起全棑
docker compose up -d --build

# 3. 開瀏覽器
open http://localhost:5173
```

| 服務 | URL | 帳密 |
|---|---|---|
| 前端 (nginx + Vite SPA) | http://localhost:5173 | — |
| 後端 (FastAPI + OpenAPI) | http://localhost:8000/docs | — |
| pgAdmin | http://localhost:5050 | admin@local.dev / admin |
| Postgres | localhost:**5433** | finsentiment / finsentiment_dev |

> Port **5433** 是刻意避開常見本機 PostgreSQL 5432 的衝突；容器內仍是 5432。

## 6 個資料來源（API 化、不寫傳統爬蟲）

| 類型 | 來源 | 用途 |
|---|---|---|
| 新聞 | Marketaux、Finnhub、NewsAPI、Alpha Vantage | 英文財經新聞；AV 自帶情緒分數可作 baseline 對照 |
| 社群 | PTT 股票版、StockTwits | 散戶情緒；StockTwits 自帶 bullish/bearish 作 ground truth |
| 內文擷取 | Jina Reader → trafilatura → snippet 三層 fallback | 把新聞 URL 轉成完整 Markdown 內文 |

## AI 設計亮點

- **Claude Haiku 4.5** 取代計劃書原訂的 FinBERT + 中文 RoBERTa 雙模型方案 — 一顆模型搞定中英文、不用扛 2.4GB torch
- **Prompt caching**：system prompt > 4096 tokens 達 Haiku 4.5 最低快取門檻，第 2 篇起 input 部分省 90% 成本
- **結構化輸出**：每篇分析回傳 `label` / `confidence` / `key_drivers` / `is_clickbait` / `reasoning`
- **標題殺人偵測**：自動標記 title vs body 情緒矛盾的新聞
- **三層 fallback 內文擷取**：Jina (主) → trafilatura (本機) → snippet (兜底)
- **實測成本**：112 篇文章 backfill = **$0.40**，10 stocks 24/7 監控 < $1.5/天

## 排程任務（APScheduler，獨立 scheduler 容器）

| Job | 頻率 | 動作 |
|---|---|---|
| `pipeline_cycle` | 每 30 min | 7 個 fetcher → 三層內文擷取 → 去重入庫 |
| `sentiment_cycle` | 每 10 min | 對未分析 rows 跑 Claude（cache 暖路徑） |
| `daily_summary` | 每天 23:00 UTC | 重算今日+昨日 `market_summary` |

## API Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/stocks?q=` | 列表 + 模糊搜尋 |
| GET | `/api/stocks/{symbol}?days=N` | 個股趨勢 + top_keywords |
| GET | `/api/market/today` | 今日 + 昨日 + change |
| GET | `/api/market/history?days=N` | 時間序列 |
| GET | `/api/market/trending?limit=N` | 排行榜 |
| GET | `/api/news?q=&symbol=&limit=N` | 新聞列表 + 情緒 snippet |
| GET | `/api/news/{id}` | 完整內文 + analysis_metadata |
| POST | `/api/auth/register` | 註冊 |
| POST | `/api/auth/login` | 取 JWT |
| GET | `/api/users/me` | 當前使用者（需 Bearer token） |

## 開發模式（不用 docker）

如果要熱重載開發，前後端可分別跑：

```bash
# Postgres 還是用 docker
docker compose up -d postgres pgadmin

# Backend
cd backend && uv sync && uv run uvicorn main:app --reload --port 8000

# Frontend
cd frontend && bun install && bun run dev
```

## API Key 申請

| 服務 | 註冊頁 | 免費額度 |
|---|---|---|
| **Anthropic**（必填） | https://console.anthropic.com/ | 按用量計費（Haiku 4.5：$1/$5 per 1M tokens） |
| Marketaux | https://www.marketaux.com/ | 100 req/day |
| Finnhub | https://finnhub.io/ | 60 req/min |
| NewsAPI | https://newsapi.org/ | 100 req/day |
| Alpha Vantage | https://www.alphavantage.co/ | 25 req/day |
| Jina Reader | https://jina.ai/ | 500 req/min（註冊後） |
| StockTwits / PTT | 無需註冊 | — |

## 測試

```bash
cd backend && uv run pytest   # 52 tests pass
cd frontend && bunx tsc --noEmit -p tsconfig.app.json   # type-check
```

## 技術棧

| 層 | 工具 |
|---|---|
| 前端 | React 19、Vite 8、TypeScript 6、Tailwind 3、Recharts、React Router 7、TanStack Query 5、Axios、Zod |
| 後端 | FastAPI、SQLAlchemy 2.0 (async)、Alembic、Pydantic v2、APScheduler、httpx、loguru、trafilatura、passlib、python-jose |
| AI | Anthropic SDK + Claude Haiku 4.5（結構化輸出 + prompt caching） |
| 資料庫 | PostgreSQL 16 |
| Container | Docker Compose（postgres + pgadmin + backend + scheduler + frontend nginx）|
