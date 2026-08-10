from datetime import date, datetime
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from app.collectors.samsung_kodex import SamsungKodexConstituentCollector
from app.core.etf_cache import SqliteEtfCache
from app.models.etf import EtfSnapshot
from app.models.holdings import EtfConstituent, EtfConstituentSnapshot
from app.services.holdings_service import get_etf_holdings


def test_kodex_constituent_parser_excludes_cash_and_invalid_weights() -> None:
    valid = SamsungKodexConstituentCollector._normalize_constituent({
        "itmNo": "005930", "secNm": "삼성전자", "ratio": "31.25", "applyQ": "10",
        "evalA": "2500000", "curp": "250000", "risep": "1000",
    })
    cash = SamsungKodexConstituentCollector._normalize_constituent({
        "itmNo": "KRD010010001", "secNm": "현금", "ratio": None,
    })

    assert valid is not None
    assert valid.constituent_code == "005930"
    assert valid.weight_percent == 31.25
    assert valid.quantity == 10
    assert cash is None


def test_cache_persists_constituent_snapshot_and_reuses_it_today() -> None:
    collected_at = datetime.now(ZoneInfo("Asia/Seoul"))
    snapshot = EtfConstituentSnapshot(
        ticker="069500", etf_name="KODEX 200", provider="KODEX official PDF", product_id="2ETF01",
        as_of_date="20260807", source_url="https://example.test/product", collected_at=collected_at,
        source_record_count=2, excluded_record_count=1,
        constituents=[EtfConstituent("005930", "삼성전자", 31.25, quantity=10)],
    )
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        cache.save_constituent_snapshot(snapshot)
        loaded = cache.load_constituents_collected_today("069500")

    assert loaded is not None
    assert loaded.as_of_date == "20260807"
    assert loaded.constituents[0].constituent_name == "삼성전자"


class StubKodexCollector:
    def collect(self, etf: EtfSnapshot) -> EtfConstituentSnapshot:
        return EtfConstituentSnapshot(
            ticker=etf.ticker, etf_name=etf.name, provider="KODEX official PDF", product_id="2ETF01",
            as_of_date=etf.as_of_date, source_url="https://example.test/product",
            collected_at=datetime.now(ZoneInfo("Asia/Seoul")), source_record_count=1,
            excluded_record_count=0, constituents=[EtfConstituent("005930", "삼성전자", 31.25)],
        )


def test_holdings_service_refreshes_kodex_then_returns_database_cache() -> None:
    etf = EtfSnapshot(
        ticker="069500", name="KODEX 200", market="ETF", close_price_krw=50_000,
        trade_volume=1_000, trade_value_krw=50_000_000, as_of_date="20260807",
        asset_types=frozenset({"equity"}), classification_source="krx",
    )
    with TemporaryDirectory() as directory:
        cache = SqliteEtfCache(f"{directory}/etf.db")
        cache.save([etf])
        refreshed = get_etf_holdings("069500", cache, StubKodexCollector())  # type: ignore[arg-type]
        cached = get_etf_holdings("069500", cache, StubKodexCollector())  # type: ignore[arg-type]

    assert refreshed.status == "available"
    assert refreshed.cache_status == "refreshed"
    assert refreshed.constituents[0].weight_percent == 31.25
    assert cached.data_origin == "database"
    assert cached.cache_status == "current"
