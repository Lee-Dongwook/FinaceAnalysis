from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.news import CollectedNewsArticle
from app.services.news_collection_service import collect_news_for_top_quantitative_candidates


class StubNewsCollector:
    def collect(self, query: str, published_from: datetime, published_to: datetime) -> list[CollectedNewsArticle]:
        return [
            CollectedNewsArticle(
                article_id=f"{query}-in", title=f"{query} 최근 기사", description="원천 설명",
                original_link=f"https://news.example.com/{query}/in", link=None,
                publisher="news.example.com",
                published_at=datetime(2026, 8, 1, 9, tzinfo=ZoneInfo("Asia/Seoul")),
            )
        ]


def test_news_collection_uses_top_ranked_etfs_and_preserves_etf_match() -> None:
    result = collect_news_for_top_quantitative_candidates(
        {"candidates": [
            {"ticker": "111111", "name": "ETF A", "score": {"status": "calculated", "rank": 2}},
            {"ticker": "222222", "name": "ETF B", "score": {"status": "calculated", "rank": 1}},
            {"ticker": "333333", "name": "ETF C", "score": None},
        ]},
        StubNewsCollector(), datetime(2026, 8, 6, 12, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert result.status == "available"
    assert [item.ticker for item in result.etfs] == ["222222", "111111"]
    assert result.collected_article_count == 2
    assert result.etfs[0].articles[0].title == "ETF B 최근 기사"
