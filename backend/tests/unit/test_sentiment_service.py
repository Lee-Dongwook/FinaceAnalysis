from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.api.schemas.analysis import EtfNewsCollection, NewsArticle, NewsCollectionResult
from app.core.etf_cache import SqliteEtfCache
from app.models.sentiment import SentimentAssessment, StoredNewsArticle
from app.services.sentiment_service import analyze_collected_news


class FixedAnalyzer:
    def analyze(self, ticker: str, name: str, articles: list[StoredNewsArticle]) -> SentimentAssessment:
        return SentimentAssessment(
            sentiment_score=72, evidence_sufficient=True, sentiment_rationale="두 기사 모두 ETF 관련 이슈를 뒷받침합니다.",
            core_issues=("금리 변화",), risk_factors=("변동성 확대",), keywords=("금리", "채권"),
            evidence_article_ids=(articles[0].article_id, articles[1].article_id),
        )


def _article(article_id: str, now: datetime) -> NewsArticle:
    return NewsArticle(article_id=article_id, title=f"news {article_id}", original_link=f"https://example.com/{article_id}", publisher="example.com", published_at=now)


def test_sentiment_persists_evidence_and_excludes_insufficient_news(tmp_path) -> None:
    cache = SqliteEtfCache(str(tmp_path / "sentiment.db"))
    now = datetime(2026, 8, 8, 10, tzinfo=ZoneInfo("Asia/Seoul"))
    collection = NewsCollectionResult(
        status="available", source="NAVER API HUB news search", search_window_start=now, search_window_end=now,
        selected_etf_count=2, collected_article_count=3, article_limit=100, message="test",
        etfs=[
            EtfNewsCollection(ticker="111111", name="ETF A", quantitative_rank=1, query="ETF A", articles=[_article("a-1", now), _article("a-2", now)]),
            EtfNewsCollection(ticker="222222", name="ETF B", quantitative_rank=2, query="ETF B", articles=[_article("b-1", now)]),
        ],
    )
    cache.save_news_collection(collection)
    result = analyze_collected_news(
        collection, cache, FixedAnalyzer(),
        SimpleNamespace(openai_sentiment_model="test-model", sentiment_minimum_articles=2, sentiment_max_parallel_requests=2),  # type: ignore[arg-type]
    )

    assert result.status == "available"
    assert result.eligible_tickers == ["111111"]
    assert result.results[0].sentiment_score == 72
    assert result.results[1].exclusion_reason == "insufficient_news"
    with cache._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM sentiment_analysis_runs").fetchone()[0] == 1
        rows = connection.execute("SELECT ticker, status, sentiment_score FROM etf_sentiment_analyses ORDER BY quantitative_rank").fetchall()
    assert [(row["ticker"], row["status"], row["sentiment_score"]) for row in rows] == [("111111", "available", 72), ("222222", "excluded", None)]
