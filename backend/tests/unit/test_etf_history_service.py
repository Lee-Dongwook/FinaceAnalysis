from datetime import date
from tempfile import TemporaryDirectory

from app.core.etf_cache import SqliteEtfCache
from app.models.etf import EtfSnapshot
from app.services.etf_history_service import (
    ensure_latest_etf_snapshot,
    ensure_twelve_month_etf_history,
    months_before,
)


class HistoryCollector:
    def __init__(self) -> None:
        self.requested_dates: list[date] = []

    def collect_for_dates(self, requested_dates: list[date]) -> list[EtfSnapshot]:
        self.requested_dates = requested_dates
        return [
            EtfSnapshot(
                ticker="069500", name="KODEX 200", market="ETF", close_price_krw=50_000,
                trade_volume=1_000, trade_value_krw=50_000_000,
                as_of_date=requested_date.strftime("%Y%m%d"),
                asset_types=frozenset({"equity"}), classification_source="krx",
            )
            for requested_date in requested_dates
        ]


def test_months_before_preserves_calendar_months() -> None:
    assert months_before(date(2026, 8, 6), 12) == date(2025, 8, 6)
    assert months_before(date(2026, 8, 31), 12) == date(2025, 8, 31)


def test_history_backfill_requests_missing_weekdays_and_persists_them() -> None:
    collector = HistoryCollector()
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        result = ensure_twelve_month_etf_history(cache, collector, reference_date=date(2026, 2, 3))
        stored_dates = cache.existing_base_dates("20250203", "20260203")

    assert result.requested_dates == len(collector.requested_dates)
    assert result.stored_records == len(collector.requested_dates)
    assert date(2025, 2, 3) in collector.requested_dates
    assert stored_dates == {requested_date.strftime("%Y%m%d") for requested_date in collector.requested_dates}


def test_history_backfill_skips_collection_when_twelve_month_history_exists() -> None:
    collector = HistoryCollector()
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        cache.save([
            EtfSnapshot(
                ticker="069500", name="KODEX 200", market="ETF", close_price_krw=50_000,
                trade_volume=1_000, trade_value_krw=50_000_000, as_of_date="20250203",
                asset_types=frozenset({"equity"}), classification_source="krx",
            )
        ])
        result = ensure_twelve_month_etf_history(cache, collector, reference_date=date(2026, 2, 3))

    assert result.requested_dates == 0
    assert collector.requested_dates == []


def test_latest_snapshot_uses_friday_cache_on_saturday() -> None:
    collector = HistoryCollector()
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        cache.save([EtfSnapshot(
            ticker="069500", name="KODEX 200", market="ETF", close_price_krw=50_000,
            trade_volume=1_000, trade_value_krw=50_000_000, as_of_date="20260807",
            asset_types=frozenset({"equity"}), classification_source="krx",
        )])
        result = ensure_latest_etf_snapshot(cache, collector, reference_date=date(2026, 8, 8))

    assert result.cache_status == "current"
    assert result.as_of_date == "20260807"
    assert collector.requested_dates == []
