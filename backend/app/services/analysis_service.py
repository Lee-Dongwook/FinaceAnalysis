import logging
import sqlite3
from uuid import uuid4

from app.api.schemas.analysis import (
    AnalysisEcho,
    AnalysisError,
    AnalysisRequest,
    AnalysisResponse,
    CandidateFilteringResult,
    EtfCandidate,
    EtfDataContext,
)
from app.collectors.krx import KrxCollectorError, KrxETFCollector
from app.collectors.naver_news import NaverNewsCollector, NaverNewsCollectorError
from app.ai.openai_sentiment import SentimentAnalyzer
from app.core.config import settings
from app.core.etf_cache import KRX_SOURCE, SqliteEtfCache
from app.quantitative.first_stage_filter import (
    CANDIDATE_LIMIT,
    RULES_VERSION,
    filter_first_stage_candidates,
)
from app.services.quantitative_service import build_quantitative_analysis
from app.services.news_collection_service import collect_news_for_top_quantitative_candidates
from app.services.sentiment_service import analyze_collected_news
from app.services.portfolio_service import build_portfolio

logger = logging.getLogger(__name__)


def run_analysis(
    request: AnalysisRequest,
    collector: KrxETFCollector | None = None,
    cache: SqliteEtfCache | None = None,
    news_collector: NaverNewsCollector | None = None,
    sentiment_analyzer: SentimentAnalyzer | None = None,
) -> AnalysisResponse:
    """Use current ETF cache or refresh it from KRX before first-stage filtering."""
    response = AnalysisResponse(
        request_id=str(uuid4()),
        status="partial",
        analysis=AnalysisEcho(
            received_conditions=request,
            message="전달된 투자 조건을 확인했습니다.",
        ),
        warnings=["뉴스 감성 분석, AI 호출, 최종 포트폴리오 구성은 아직 구현되지 않았습니다."],
        disclaimer="이 서비스는 정보 제공 목적이며 투자 성과를 보장하지 않습니다.",
    )
    response.warnings = ["포트폴리오 결과는 정보 제공용이며, 정량 점수와 검증된 뉴스 근거를 함께 표시합니다."]
    try:
        etf_cache = cache or SqliteEtfCache(settings.etf_database_path)
        cached_snapshot = etf_cache.load_if_current()
        if cached_snapshot is None:
            cached_snapshot = etf_cache.save((collector or KrxETFCollector()).collect_latest())
            data_origin = "krx"
            cache_status = "refreshed"
        else:
            data_origin = "database"
            cache_status = "current"
        snapshots = cached_snapshot.snapshots
        result = filter_first_stage_candidates(snapshots, request)
    except (KrxCollectorError, sqlite3.Error, ValueError) as error:
        logger.warning(
            "analysis_etf_data_stage_failed request_id=%s error_type=%s",
            response.request_id,
            type(error).__name__,
        )
        response.errors.append(
            AnalysisError(
                scope="etf_collection",
                code="krx_collection_unavailable",
                message="KRX ETF 데이터를 수집하지 못했습니다. 환경 설정과 API 활용 승인 상태를 확인해주세요.",
                retryable=True,
            )
        )
        return response

    candidates = [
        EtfCandidate(
            ticker=match.snapshot.ticker,
            name=match.snapshot.name,
            market=match.snapshot.market,
            asset_types=sorted(match.snapshot.asset_types),
            classification_source=match.snapshot.classification_source,
            close_price_krw=match.snapshot.close_price_krw,
            trade_volume=match.snapshot.trade_volume,
            trade_value_krw=match.snapshot.trade_value_krw,
            as_of_date=match.snapshot.as_of_date,
            affordable_units=match.affordable_units,
            matched_preferred_asset_types=list(match.matched_preferred_assets),
            matched_theme_industry_keywords=list(match.matched_theme_industry_keywords),
        )
        for match in result.candidates
    ]
    response.candidate_filtering = CandidateFilteringResult(
        collected_count=result.collected_count,
        eligible_count=result.eligible_count,
        excluded_count=len(result.excluded),
        candidate_limit=CANDIDATE_LIMIT,
        rules_version=RULES_VERSION,
        candidates=candidates,
    )
    response.quantitative_analysis = build_quantitative_analysis(
        result.candidates, request.quantitative_analysis_period_months, cached_snapshot.as_of_date,
        etf_cache, settings.weekly_sample_weekday, settings.kofr_annual_rate_percent,
        request.risk_profile,
    )
    try:
        response.news_collection = collect_news_for_top_quantitative_candidates(
            response.quantitative_analysis, news_collector,
        )
        response.news_collection.stored_article_count = etf_cache.save_news_collection(
            response.news_collection
        )
        if response.news_collection.etfs:
            response.sentiment_analysis = analyze_collected_news(
                response.news_collection, etf_cache, sentiment_analyzer,
            )
    except NaverNewsCollectorError as error:
        logger.warning(
            "analysis_news_collection_failed request_id=%s error_type=%s",
            response.request_id, type(error).__name__,
        )
        response.errors.append(
            AnalysisError(
                scope="news_collection", code="naver_news_collection_unavailable",
                message="NAVER 뉴스 데이터를 수집하지 못했습니다. API HUB 인증과 사용 설정을 확인해 주세요.",
                retryable=True,
            )
        )
    except sqlite3.Error as error:
        logger.warning(
            "analysis_news_storage_failed request_id=%s error_type=%s",
            response.request_id, type(error).__name__,
        )
        response.errors.append(
            AnalysisError(
                scope="news_storage", code="news_storage_unavailable",
                message="수집한 뉴스 데이터를 SQLite에 저장하지 못했습니다.",
                retryable=True,
            )
        )
    response.portfolio = build_portfolio(
        request, result.candidates, response.quantitative_analysis, response.sentiment_analysis,
    )
    as_of_dates = sorted({snapshot.as_of_date for snapshot in snapshots})
    response.data_context = EtfDataContext(
        source=KRX_SOURCE,
        retrieved_at=cached_snapshot.collected_at,
        as_of_date=as_of_dates[-1] if len(as_of_dates) == 1 else None,
        data_origin=data_origin,
        cache_status=cache_status,
    )
    if not candidates:
        response.warnings.append("입력 조건을 만족하는 1차 ETF 후보가 없습니다.")
    return response
