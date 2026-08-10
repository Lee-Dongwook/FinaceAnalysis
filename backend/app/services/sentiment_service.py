import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.ai.openai_sentiment import OpenAiSentimentAnalyzer, SentimentAnalyzer, SentimentAnalyzerError
from app.api.schemas.analysis import EtfNewsCollection, NewsCollectionResult, SentimentAnalysisResult, SentimentEtfResult
from app.core.config import Settings, settings
from app.core.etf_cache import SqliteEtfCache
from app.models.sentiment import SentimentAssessment, StoredNewsArticle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PreparedEtf:
    etf: EtfNewsCollection
    articles: list[StoredNewsArticle]


def analyze_collected_news(collection: NewsCollectionResult, cache: SqliteEtfCache, analyzer: SentimentAnalyzer | None = None, app_settings: Settings = settings) -> SentimentAnalysisResult:
    """Analyze only this request's persisted news rows and store every ETF outcome."""
    if collection.stored_at is None:
        raise ValueError("News collection must be stored before sentiment analysis.")
    source_articles = cache.load_news_for_collection(collection.stored_at)
    prepared = [_PreparedEtf(etf, source_articles.get(etf.ticker, [])) for etf in collection.etfs]
    results: list[SentimentEtfResult] = []
    ready = [item for item in prepared if len(item.articles) >= app_settings.sentiment_minimum_articles]
    for item in prepared:
        if len(item.articles) < app_settings.sentiment_minimum_articles:
            results.append(_excluded_result(item, "insufficient_news"))
    if ready:
        active_analyzer = analyzer or OpenAiSentimentAnalyzer(app_settings)
        workers = min(max(app_settings.sentiment_max_parallel_requests, 1), len(ready))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sentiment") as executor:
            futures = {executor.submit(active_analyzer.analyze, item.etf.ticker, item.etf.name, item.articles): item for item in ready}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    results.append(_assessment_result(item, future.result(), app_settings.sentiment_minimum_articles))
                except SentimentAnalyzerError:
                    logger.warning("sentiment_analysis_failed ticker=%s", item.etf.ticker)
                    results.append(_unavailable_result(item))
                except Exception:
                    logger.exception("sentiment_analysis_unexpected_failure ticker=%s", item.etf.ticker)
                    results.append(_unavailable_result(item))
    results.sort(key=lambda item: item.quantitative_rank)
    analyzed_at = datetime.now(ZoneInfo("Asia/Seoul"))
    output = SentimentAnalysisResult(
        status="available" if any(item.status == "available" for item in results) else "insufficient_evidence",
        run_id=str(uuid4()), source="OpenAI Responses API", model=app_settings.openai_sentiment_model,
        minimum_articles=app_settings.sentiment_minimum_articles,
        maximum_parallel_requests=max(app_settings.sentiment_max_parallel_requests, 1), analyzed_at=analyzed_at,
        eligible_tickers=[item.ticker for item in results if item.status == "available"], results=results,
    )
    cache.save_sentiment_analysis(output)
    return output


def _assessment_result(item: _PreparedEtf, assessment: SentimentAssessment, minimum_articles: int) -> SentimentEtfResult:
    permitted = {article.article_id for article in item.articles}
    evidence = list(dict.fromkeys(article_id for article_id in assessment.evidence_article_ids if article_id in permitted))
    if not assessment.evidence_sufficient or len(evidence) < minimum_articles or not assessment.sentiment_rationale:
        return _excluded_result(item, "insufficient_evidence", assessment)
    return SentimentEtfResult(
        ticker=item.etf.ticker, name=item.etf.name, quantitative_rank=item.etf.quantitative_rank,
        article_count=len(item.articles), status="available", exclusion_reason=None,
        sentiment_score=assessment.sentiment_score, sentiment_rationale=assessment.sentiment_rationale,
        core_issues=list(assessment.core_issues), risk_factors=list(assessment.risk_factors),
        keywords=list(assessment.keywords), evidence_article_ids=evidence,
    )


def _excluded_result(item: _PreparedEtf, reason: str, assessment: SentimentAssessment | None = None) -> SentimentEtfResult:
    return SentimentEtfResult(
        ticker=item.etf.ticker, name=item.etf.name, quantitative_rank=item.etf.quantitative_rank,
        article_count=len(item.articles), status="excluded", exclusion_reason=reason,
        sentiment_score=assessment.sentiment_score if assessment else None,
        sentiment_rationale=assessment.sentiment_rationale if assessment else None,
        core_issues=list(assessment.core_issues) if assessment else [],
        risk_factors=list(assessment.risk_factors) if assessment else [],
        keywords=list(assessment.keywords) if assessment else [],
        evidence_article_ids=list(assessment.evidence_article_ids) if assessment else [],
    )


def _unavailable_result(item: _PreparedEtf) -> SentimentEtfResult:
    return SentimentEtfResult(
        ticker=item.etf.ticker, name=item.etf.name, quantitative_rank=item.etf.quantitative_rank,
        article_count=len(item.articles), status="unavailable", exclusion_reason="llm_unavailable",
        sentiment_score=None, sentiment_rationale=None, core_issues=[], risk_factors=[], keywords=[], evidence_article_ids=[],
    )
