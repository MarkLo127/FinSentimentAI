from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://finsentiment:finsentiment_dev@localhost:5433/finsentiment"
    )

    marketaux_api_key: str = ""
    finnhub_api_key: str = ""
    newsapi_key: str = ""
    alpha_vantage_key: str = ""

    jina_api_key: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"

    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Google Sign-In. The Client ID is a public identifier (safe to ship to the
    # frontend); we still verify ID tokens server-side against it.
    google_client_id: str = ""

    news_fetch_interval_minutes: int = 30
    social_fetch_interval_minutes: int = 60
    daily_summary_hour: int = 23
    sentiment_analysis_batch_size: int = 10
    monitored_tickers: str = "TSM"  # comma-separated list of tickers to monitor

    @property
    def monitored_ticker_list(self) -> list[str]:
        return [t.strip().upper() for t in self.monitored_tickers.split(",") if t.strip()]

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
