from datetime import datetime
from zoneinfo import ZoneInfo

from app.api.schemas.analysis import EtfNewsCollection, NewsArticle, NewsCollectionResult
from app.core.etf_cache import SqliteEtfCache


def test_news_collection_is_saved_with_etf_match(tmp_path) -> None:
    cache = SqliteEtfCache(str(tmp_path / "news.db"))
    now = datetime(2026, 8, 6, 9, tzinfo=ZoneInfo("Asia/Seoul"))
    collection = NewsCollectionResult(
        status="available", source="NAVER API HUB news search", search_window_start=now,
        search_window_end=now, selected_etf_count=1, collected_article_count=1,
        article_limit=100, message="test",
        etfs=[EtfNewsCollection(
            ticker="069500", name="KODEX 200", quantitative_rank=1, query="KODEX 200",
            articles=[NewsArticle(
                article_id="article-1", title="news", original_link="https://example.com/news",
                publisher="example.com", published_at=now,
            )],
        )],
    )

    assert cache.save_news_collection(collection) == 1
    with cache._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM etf_news_matches").fetchone()[0] == 1
