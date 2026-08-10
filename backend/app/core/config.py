from dataclasses import dataclass
from os import environ, getenv
from pathlib import Path


def load_project_env() -> None:
    """Load local development variables without overriding deployed environment values."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_project_env()


def optional_float(name: str) -> float | None:
    value = getenv(name)
    return float(value) if value not in (None, "") else None


def optional_int(name: str) -> int | None:
    value = getenv(name)
    return int(value) if value not in (None, "") else None


@dataclass(frozen=True)
class Settings:
    app_env: str = getenv("APP_ENV", "development")
    allowed_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in getenv(
            "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    )
    krx_api_key: str | None = getenv("KRX_API_KEY")
    etf_database_path: str = getenv("ETF_DATABASE_PATH", "data/finance_analysis.db")
    krx_request_timeout_seconds: float = float(
        getenv("KRX_REQUEST_TIMEOUT_SECONDS", "15")
    )
    samsung_fund_base_url: str = getenv("SAMSUNG_FUND_BASE_URL", "https://www.samsungfund.com")
    samsung_fund_request_timeout_seconds: float = float(
        getenv("SAMSUNG_FUND_REQUEST_TIMEOUT_SECONDS", "15")
    )
    naver_api_key_id: str | None = getenv("NAVER_API_KEY_ID")
    naver_api_key: str | None = getenv("NAVER_API_KEY")
    naver_news_request_timeout_seconds: float = float(
        getenv("NAVER_NEWS_REQUEST_TIMEOUT_SECONDS", "10")
    )
    news_relevance_threshold: float = float(getenv("NEWS_RELEVANCE_THRESHOLD", "0.12"))
    openai_api_key: str | None = getenv("OPENAI_API_KEY")
    openai_sentiment_model: str | None = getenv("OPENAI_SENTIMENT_MODEL")
    openai_request_timeout_seconds: float = float(
        getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "30")
    )
    sentiment_minimum_articles: int = int(getenv("SENTIMENT_MINIMUM_ARTICLES", "2"))
    sentiment_max_parallel_requests: int = int(
        getenv("SENTIMENT_MAX_PARALLEL_REQUESTS", "4")
    )
    kofr_annual_rate_percent: float = optional_float("KOFR_ANNUAL_RATE_PERCENT") or 3.0
    weekly_sample_weekday: int = optional_int("WEEKLY_SAMPLE_WEEKDAY") if optional_int("WEEKLY_SAMPLE_WEEKDAY") is not None else 4


settings = Settings()
