import calendar
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from app.collectors.krx import KrxETFCollector
from app.core.etf_cache import SqliteEtfCache


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EtfHistorySyncResult:
    start_date: date
    end_date: date
    requested_dates: int
    stored_records: int


@dataclass(frozen=True)
class LatestEtfSyncResult:
    expected_date: date
    as_of_date: str | None
    stored_records: int
    cache_status: str


def months_before(reference_date: date, months: int) -> date:
    """Return the calendar date ``months`` before ``reference_date``."""
    month_index = reference_date.year * 12 + reference_date.month - 1 - months
    year, month_zero_index = divmod(month_index, 12)
    month = month_zero_index + 1
    day = min(reference_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def ensure_latest_etf_snapshot(
    cache: SqliteEtfCache,
    collector: KrxETFCollector,
    reference_date: date | None = None,
) -> LatestEtfSyncResult:
    """Ensure the database contains the latest weekday ETF snapshot on startup."""
    expected_date = cache.latest_weekday_date(reference_date)
    cached = cache.load_if_current(reference_date)
    if cached is not None:
        return LatestEtfSyncResult(
            expected_date, cached.as_of_date, stored_records=0, cache_status="current"
        )
    snapshots = collector.collect_latest()
    saved = cache.save(snapshots)
    return LatestEtfSyncResult(
        expected_date, saved.as_of_date, stored_records=len(saved.snapshots),
        cache_status="refreshed",
    )


def ensure_twelve_month_etf_history(
    cache: SqliteEtfCache,
    collector: KrxETFCollector,
    reference_date: date | None = None,
) -> EtfHistorySyncResult:
    """Backfill missing weekday ETF snapshots for the latest twelve calendar months."""
    end_date = reference_date or date.today()
    start_date = months_before(end_date, 12)
    if cache.has_history_through(start_date.strftime("%Y%m%d")):
        return EtfHistorySyncResult(start_date, end_date, requested_dates=0, stored_records=0)
    existing_dates = cache.existing_base_dates(
        start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")
    )
    requested_dates = [
        current_date
        for offset in range((end_date - start_date).days + 1)
        if (current_date := start_date + timedelta(days=offset)).weekday() < 5
        and current_date.strftime("%Y%m%d") not in existing_dates
    ]
    if not requested_dates:
        return EtfHistorySyncResult(start_date, end_date, requested_dates=0, stored_records=0)

    logger.info(
        "etf_history_backfill_started start_date=%s end_date=%s missing_weekdays=%s",
        start_date.isoformat(), end_date.isoformat(), len(requested_dates),
    )
    snapshots = collector.collect_for_dates(requested_dates)
    if snapshots:
        cache.save(snapshots)
    logger.info(
        "etf_history_backfill_completed requested_dates=%s stored_records=%s",
        len(requested_dates), len(snapshots),
    )
    return EtfHistorySyncResult(
        start_date=start_date,
        end_date=end_date,
        requested_dates=len(requested_dates),
        stored_records=len(snapshots),
    )
