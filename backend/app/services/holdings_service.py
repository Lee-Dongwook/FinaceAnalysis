import logging

from app.api.schemas.analysis import EtfHoldingsResponse
from app.collectors.samsung_kodex import (
    KODEX_PROVIDER,
    KodexConstituentCollectorError,
    SamsungKodexConstituentCollector,
)
from app.core.etf_cache import SqliteEtfCache
from app.models.holdings import EtfConstituentSnapshot


logger = logging.getLogger(__name__)


class EtfHoldingsNotFoundError(Exception):
    pass


def get_etf_holdings(
    ticker: str,
    cache: SqliteEtfCache,
    collector: SamsungKodexConstituentCollector | None = None,
) -> EtfHoldingsResponse:
    """Return a KODEX ETF's official constituents, refreshing at most once per day."""
    etf = cache.load_current_ticker(ticker)
    if etf is None:
        raise EtfHoldingsNotFoundError(ticker)

    cached = cache.load_constituents_collected_today(ticker)
    if cached is not None:
        return _response_from_snapshot(cached, data_origin="database", cache_status="current")

    if not etf.name.upper().startswith("KODEX"):
        message = "현재는 KODEX ETF의 운용사 공식 구성종목 PDF만 지원합니다."
        cache.save_constituent_collection_failure(
            ticker=ticker, etf_name=etf.name, status="unsupported_provider", message=message,
        )
        return EtfHoldingsResponse(
            status="unsupported_provider", ticker=ticker, etf_name=etf.name,
            source=KODEX_PROVIDER, data_origin="none", cache_status="unavailable",
            message=message,
        )

    try:
        snapshot = (collector or SamsungKodexConstituentCollector()).collect(etf)
    except KodexConstituentCollectorError:
        logger.warning("etf_holdings_collection_failed ticker=%s", ticker)
        message = "운용사 공식 구성종목 데이터를 지금 가져오지 못했습니다. 잠시 후 다시 시도하세요."
        cache.save_constituent_collection_failure(
            ticker=ticker, etf_name=etf.name, status="source_unavailable", message=message,
        )
        return EtfHoldingsResponse(
            status="source_unavailable", ticker=ticker, etf_name=etf.name,
            source=KODEX_PROVIDER, data_origin="none", cache_status="unavailable",
            message=message,
        )

    cache.save_constituent_snapshot(snapshot)
    return _response_from_snapshot(snapshot, data_origin="official_site", cache_status="refreshed")


def _response_from_snapshot(
    snapshot: EtfConstituentSnapshot,
    data_origin: str,
    cache_status: str,
) -> EtfHoldingsResponse:
    return EtfHoldingsResponse(
        status="available",
        ticker=snapshot.ticker,
        etf_name=snapshot.etf_name,
        as_of_date=snapshot.as_of_date,
        collected_at=snapshot.collected_at,
        source=snapshot.provider,
        source_url=snapshot.source_url,
        data_origin=data_origin,
        cache_status=cache_status,
        source_record_count=snapshot.source_record_count,
        excluded_record_count=snapshot.excluded_record_count,
        constituents=[
            {
                "constituent_code": item.constituent_code,
                "constituent_name": item.constituent_name,
                "weight_percent": item.weight_percent,
                "quantity": item.quantity,
                "evaluation_amount_krw": item.evaluation_amount_krw,
                "current_price_krw": item.current_price_krw,
                "price_change_krw": item.price_change_krw,
            }
            for item in snapshot.constituents
        ],
        message="운용사 공식 구성종목 PDF 기준 데이터입니다. 현금성 자산 또는 편입비중이 없는 항목은 제외했습니다.",
    )
