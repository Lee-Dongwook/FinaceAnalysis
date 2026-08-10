from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.api.schemas.analysis import (
    EtfNewsCollection, NewsCandidateAnalysisResponse, NewsCandidateAnalysisRequest,
    NewsArticle, NewsCollectionResult, ValidatedNewsArticleResponse,
)
from app.collectors.naver_news import NaverNewsCollector
from app.core.config import Settings, settings
from app.core.etf_cache import SqliteEtfCache
from app.services.news_validation_service import validate_news_articles
from app.services.sentiment_service import analyze_collected_news


class CandidateNewsNotFoundError(Exception):
    pass


def analyze_one_candidate_news(request: NewsCandidateAnalysisRequest, cache: SqliteEtfCache, collector: NaverNewsCollector | None = None, app_settings: Settings = settings) -> NewsCandidateAnalysisResponse:
    snapshot = cache.load_current_ticker(request.ticker)
    if snapshot is None:
        raise CandidateNewsNotFoundError("ETF ticker is not in the current cache.")
    end = datetime.now(ZoneInfo("Asia/Seoul"))
    start = end - timedelta(days=30)
    keywords = _keywords(snapshot.name, snapshot.ticker, snapshot.raw_classification, request.additional_keywords)
    source = collector or NaverNewsCollector(app_settings)
    raw_articles = [article for query in keywords for article in source.collect(query, start, end)]
    validated = validate_news_articles(raw_articles, keywords, start, end, app_settings.news_relevance_threshold)
    response_articles = [ValidatedNewsArticleResponse(
        article_id=item.article.article_id, title=item.article.title, description=item.article.description,
        original_link=item.article.original_link, link=item.article.link, publisher=item.article.publisher,
        published_at=item.article.published_at, relevance_score=round(item.relevance_score, 4),
    ) for item in validated]
    if not validated:
        return NewsCandidateAnalysisResponse(status="no_news", ticker=snapshot.ticker, name=snapshot.name, search_keywords=keywords,
            search_window_start=start, search_window_end=end, relevance_threshold=app_settings.news_relevance_threshold, articles=[])
    collection = NewsCollectionResult(status="available", source="NAVER API HUB news search", search_window_start=start, search_window_end=end,
        selected_etf_count=1, collected_article_count=len(validated), article_limit=len(validated), message="Validated ETF news",
        etfs=[EtfNewsCollection(ticker=snapshot.ticker, name=snapshot.name, quantitative_rank=1, query=" | ".join(keywords),
            articles=[NewsArticle(article_id=item.article.article_id, title=item.article.title, description=item.article.description,
                original_link=item.article.original_link, link=item.article.link, publisher=item.article.publisher, published_at=item.article.published_at) for item in validated])])
    cache.save_news_collection(collection)
    sentiment = analyze_collected_news(collection, cache, app_settings=app_settings).results[0]
    return NewsCandidateAnalysisResponse(status="available" if sentiment.status == "available" else "analysis_unavailable", ticker=snapshot.ticker,
        name=snapshot.name, search_keywords=keywords, search_window_start=start, search_window_end=end,
        relevance_threshold=app_settings.news_relevance_threshold, articles=response_articles, sentiment=sentiment)


def _keywords(name: str, ticker: str, index_name: str | None, additional: list[str]) -> list[str]:
    values = [name, ticker, *(part.strip() for part in (index_name or "").replace("/", " ").split() if len(part.strip()) >= 2), *additional]
    return list(dict.fromkeys(value for value in values if value.strip()))[:12]
