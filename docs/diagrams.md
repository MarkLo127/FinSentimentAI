# FinSentiment AI — ER 圖與流程圖

> 圖以 Mermaid 撰寫，GitHub、VS Code（Markdown Preview Mermaid）、Obsidian 皆可直接渲染。

---

## 1. ER 圖（資料模型）

多租戶核心不變量：所有資料都掛在 `users` 之下。`stocks` 與 `refresh_jobs` 直接帶 `user_id`；
`news` / `comments` / `sentiment_results` / `market_summary` 透過 `stock_id` 繼承隔離。

```mermaid
erDiagram
    users ||--o{ stocks : owns
    users ||--o{ refresh_jobs : triggers
    users ||--o{ app_settings : "has encrypted keys"

    stocks ||--o{ news : "has"
    stocks ||--o{ comments : "has"
    stocks ||--o{ sentiment_results : "scoped to"
    stocks ||--o{ market_summary : "daily rollup"

    news ||--o{ sentiment_results : "analyzed into"
    comments ||--o{ sentiment_results : "analyzed into"
    news ||--o{ news_translations : "lazily translated"

    users {
        int id PK
        string username UK
        string email UK
        string google_sub UK "Google sub claim"
        string password_hash "nullable"
        datetime created_at
        datetime updated_at
    }

    stocks {
        int id PK
        int user_id FK
        string symbol "uq(user_id,symbol)"
        string name
        string exchange "nullable"
        string sector "nullable"
        datetime created_at
    }

    news {
        int id PK
        int stock_id FK
        text title
        text url
        string url_hash "uq(stock_id,url_hash)"
        string source "marketaux|finnhub|newsapi|alpha_vantage"
        string language
        text summary "nullable"
        text full_content "nullable"
        string fetched_via "jina|trafilatura|snippet"
        int content_length "nullable"
        datetime published_at
        datetime fetched_at
    }

    comments {
        int id PK
        int stock_id FK
        string platform "ptt|stocktwits"
        text post_title "nullable"
        text content
        string author "nullable"
        text post_url "nullable"
        string url_hash "uq(stock_id,url_hash)"
        jsonb platform_metadata "push/boo or bullish/bearish"
        datetime published_at
        datetime fetched_at
    }

    sentiment_results {
        int id PK
        int news_id FK "XOR comment_id"
        int comment_id FK "XOR news_id"
        int stock_id FK
        string sentiment_label "positive|negative|neutral"
        float confidence
        text analyzed_text "nullable"
        string model_version "claude-haiku-4-5 | alpha_vantage_v1"
        jsonb analysis_metadata "key_drivers,is_clickbait,reasoning"
        datetime analyzed_at
    }

    market_summary {
        int id PK
        int stock_id FK
        date summary_date "uq(stock_id,summary_date)"
        float sentiment_score "nullable"
        int positive_count
        int negative_count
        int neutral_count
        int total_count
        string_array top_keywords "nullable"
        datetime created_at
    }

    news_translations {
        int id PK
        int news_id FK
        string target_language "uq(news_id,target_language)"
        string translated_title "nullable"
        text translated_body "nullable"
        string model_version
        datetime created_at
    }

    refresh_jobs {
        int id PK
        int user_id FK
        string symbol
        string state "queued|running|succeeded|failed"
        string progress_stage "fetching|analyzing|summarizing"
        datetime started_at "nullable"
        datetime completed_at "nullable"
        int new_news
        int new_comments
        int sentiment_analyzed
        text error "nullable"
        datetime created_at
    }

    app_settings {
        int user_id PK "FK to users"
        string key PK "anthropic|jina|marketaux|..."
        text value "Fernet ciphertext"
        datetime updated_at
    }
```

**模型重點**
- `sentiment_results` 有 `CheckConstraint`：`news_id` 與 `comment_id` 二擇一（XOR）。
- `app_settings` 用複合主鍵 `(user_id, key)`，`value` 以 Fernet 加密（金鑰由 `SECRET_KEY` 推導）。
- `url_hash` 唯一性是「每 stock」而非全域 → 同一篇公開文章可在兩位使用者底下各存一份、各自分析。
- 無 operator fallback 金鑰：使用者沒設某來源的 key 就不抓該來源。

---

## 2. 流程圖 — On-demand Refresh（核心非同步管線）

`POST /api/stocks/{symbol}/refresh` 立即回 202，工作交給 detached task；瀏覽器每 2 秒輪詢 job 狀態。

```mermaid
flowchart TD
    A["使用者點『刷新』<br/>POST /api/stocks/{symbol}/refresh"] --> B["建立 refresh_jobs 列<br/>state=queued"]
    B --> C["asyncio.create_task<br/>(detached, 自有 DB session)"]
    C --> D["HTTP 202 + job_id 立即回傳"]
    D --> E["瀏覽器每 2s 輪詢<br/>GET /api/refresh-jobs/{id}"]

    C --> SEM{"Semaphore(2)<br/>限制全域併發"}
    SEM --> K["載入該 user 加密金鑰<br/>get_user_keys(user_id)"]
    K --> KCHK{"有 anthropic key?"}
    KCHK -- 否 --> FAIL["state=failed<br/>『missing ANTHROPIC_API_KEY』"]
    KCHK -- 是 --> F["stage=fetching<br/>pipeline.run_for_ticker"]

    F --> F1["6 fetchers 並行<br/>Marketaux / Finnhub / NewsAPI /<br/>AlphaVantage / StockTwits / PTT"]
    F1 --> F2["內文擷取 3 層 fallback<br/>Jina → trafilatura → snippet"]
    F2 --> F3["dedupe (stock_id,url_hash)<br/>ON CONFLICT DO NOTHING<br/>寫入 news / comments"]
    F3 --> F4["AlphaVantage baseline →<br/>sentiment_results(alpha_vantage_v1)"]

    F4 --> G["stage=analyzing<br/>backfill_sentiment.run"]
    G --> G1["對未分析 rows 呼叫<br/>Claude Haiku 4.5<br/>(system prompt >4096 → prompt cache)"]
    G1 --> G2["寫入 sentiment_results<br/>雙語 + is_clickbait"]

    G2 --> H["stage=summarizing<br/>daily_summary.run_for_date<br/>(昨天 + 今天)"]
    H --> H1["重算 market_summary<br/>counts / score / top_keywords"]
    H1 --> OK["state=succeeded<br/>completed_at 設定"]

    E -.->|輪詢讀取| B
    E -.->|讀到 succeeded/failed 停止| OK
    OK --> Z["前端 React Query<br/>refetch 看板資料"]
    FAIL --> Z

    classDef fail fill:#fde,stroke:#c33;
    class FAIL,KCHK fail;
```

**啟動時清理**：backend 啟動會把 `running` 超過 30 分鐘的 job 標為 `failed`（容器重啟殘留）。

---

## 3. 流程圖 — 認證 / 請求授權

```mermaid
sequenceDiagram
    participant U as 瀏覽器 (SPA)
    participant G as Google
    participant B as Backend (FastAPI)
    participant DB as Postgres

    U->>G: Google 登入
    G-->>U: ID token (含 sub)
    U->>B: POST /api/auth/google { id_token }
    B->>G: 驗證 ID token (google_client_id)
    B->>DB: upsert users by google_sub
    B-->>U: 簽發 app JWT
    Note over U: JWT 存 localStorage<br/>finsentiment.token

    U->>B: 任意 /api/* 請求<br/>Authorization: Bearer <JWT>
    B->>B: current_user 驗證 JWT
    alt JWT 有效
        B->>DB: 查詢時一律 filter user_id
        DB-->>B: 僅該 user 的資料
        B-->>U: 200 回傳
    else 無效 / 過期
        B-->>U: 401
        U->>U: RequireAuth 導向 /login
    end
```

---

## 4. 三處 LLM 用途（皆 Claude Haiku 4.5）

```mermaid
flowchart LR
    subgraph S1["① 情緒分析 sentiment_analyzer"]
        A1["全文 body"] --> A2["system prompt >4096<br/>prompt cache ✅"] --> A3["SentimentAnalysis<br/>雙語 + is_clickbait"]
    end
    subgraph S2["② 即時翻譯 translator"]
        B1["title + body"] --> B2["極簡 prompt<br/>不用 cache (每篇都唯一)"] --> B3["news_translations 快取"]
    end
    subgraph S3["③ AlphaVantage baseline"]
        C1["第三方情緒分數"] --> C2["model_version=<br/>alpha_vantage_v1"]
    end
```

| 用途 | 觸發 | Prompt cache | 落地表 |
|------|------|-------------|--------|
| 情緒分析 | refresh / `backfill_sentiment` | ✅ (system >4096 token) | `sentiment_results` |
| 即時翻譯 | `GET /api/news/{id}/translation/{lang}` | ❌（刻意關閉） | `news_translations` |
| AV baseline | pipeline 抓 AlphaVantage 時 | — | `sentiment_results` |
