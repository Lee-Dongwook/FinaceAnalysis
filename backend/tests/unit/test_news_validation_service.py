from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.news import CollectedNewsArticle
from app.services.news_validation_service import validate_news_articles


def _article(article_id: str, title: str, description: str, now: datetime, url: str) -> CollectedNewsArticle:
    return CollectedNewsArticle(article_id, title, description, url, None, "example.com", now)


def test_validates_relevance_and_removes_duplicate_urls() -> None:
    now = datetime(2026, 8, 8, tzinfo=ZoneInfo("Asia/Seoul"))
    kept = _article("1", "KODEX 반도체 ETF 수요", "KODEX 반도체 지수 관련 기사", now, "https://example.com/a?utm_source=x")
    duplicate = _article("2", "KODEX 반도체 ETF 수요", "KODEX 반도체 지수 관련 기사", now - timedelta(minutes=1), "https://example.com/a")
    unrelated = _article("3", "해외 날씨", "휴가철 여행 기사", now, "https://example.com/weather")
    result = validate_news_articles([kept, duplicate, unrelated], ["KODEX", "반도체", "반도체 지수"], now - timedelta(days=30), now, .12)
    assert [item.article.article_id for item in result] == ["1"]
    assert result[0].relevance_score >= .12
