from datetime import date
from tempfile import TemporaryDirectory

from app.core.etf_cache import SqliteEtfCache
from app.models.etf import EtfSnapshot


def test_cache_persists_and_loads_current_etf_snapshot() -> None:
    snapshot = EtfSnapshot(
        ticker="069500", name="KODEX 200", market=None, close_price_krw=50_000,
        trade_volume=1_000, trade_value_krw=50_000_000, as_of_date="20260804",
        asset_types=frozenset({"equity"}), classification_source="krx",
        raw_classification="코스피 200", nav=50_020.5, net_assets_krw=1_000_000_000,
    )
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        assert cache.load_if_current() is None

        cache.save([snapshot])
        loaded = cache.load_if_current(reference_date=date(2026, 8, 4))

    assert loaded is not None
    assert loaded.as_of_date == "20260804"
    assert loaded.snapshots[0].ticker == "069500"
    assert loaded.snapshots[0].nav == 50_020.5


def test_cache_uses_friday_snapshot_on_saturday() -> None:
    snapshot = EtfSnapshot(
        ticker="069500", name="KODEX 200", market=None, close_price_krw=50_000,
        trade_volume=1_000, trade_value_krw=50_000_000, as_of_date="20260807",
        asset_types=frozenset({"equity"}), classification_source="krx",
    )
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        cache.save([snapshot])
        loaded = cache.load_if_current(reference_date=date(2026, 8, 8))

    assert loaded is not None
    assert loaded.as_of_date == "20260807"


def test_cache_persists_multiple_base_dates() -> None:
    snapshots = [
        EtfSnapshot(
            ticker="069500", name="KODEX 200", market=None, close_price_krw=50_000,
            trade_volume=1_000, trade_value_krw=50_000_000, as_of_date=base_date,
            asset_types=frozenset({"equity"}), classification_source="krx",
        )
        for base_date in ("20260205", "20260206")
    ]
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        cache.save(snapshots)
        stored_dates = cache.existing_base_dates("20260201", "20260228")

    assert stored_dates == {"20260205", "20260206"}
