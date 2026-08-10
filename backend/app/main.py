import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyses, health, holdings, news
from app.collectors.krx import KrxCollectorError, KrxETFCollector
from app.core.config import settings
from app.core.etf_cache import SqliteEtfCache
from app.core.logging import configure_logging
from app.services.etf_history_service import (
    ensure_latest_etf_snapshot,
    ensure_twelve_month_etf_history,
)


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        latest = ensure_latest_etf_snapshot(
            cache=SqliteEtfCache(settings.etf_database_path),
            collector=KrxETFCollector(),
        )
        logger.info(
            "etf_latest_snapshot_startup_check_completed expected_date=%s as_of_date=%s cache_status=%s stored_records=%s",
            latest.expected_date.isoformat(), latest.as_of_date, latest.cache_status,
            latest.stored_records,
        )
        result = ensure_twelve_month_etf_history(
            cache=SqliteEtfCache(settings.etf_database_path),
            collector=KrxETFCollector(),
        )
        logger.info(
            "etf_history_startup_check_completed requested_dates=%s stored_records=%s",
            result.requested_dates,
            result.stored_records,
        )
    except KrxCollectorError as error:
        logger.warning("etf_history_startup_check_failed error_type=%s", type(error).__name__)
    yield


app = FastAPI(title="Finance Analysis MVP API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health.router)
app.include_router(analyses.router)
app.include_router(holdings.router)
app.include_router(news.router)
