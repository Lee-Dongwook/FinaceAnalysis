import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.api.schemas.analysis import EtfNewsCollection, NewsArticle, NewsCollectionResult
from app.collectors.naver_news import NaverNewsCollector, NaverNewsCollectorError


logger = logging.getLogger(__name__)
NEWS_ETF_LIMIT = 30
NEWS_ARTICLE_LIMIT = 100


def collect_news_for_top_quantitative_candidates(
    quantitative_analysis: dict[str, object] | None,
    collector: NaverNewsCollector | None = None,
    now: datetime | None = None,
) -> NewsCollectionResult:
    """Collect source articles for ranked ETFs without relevance or sentiment analysis."""
    search_end = (now or datetime.now(ZoneInfo("Asia/Seoul"))).astimezone(ZoneInfo("Asia/Seoul"))
    search_start = search_end - timedelta(days=30)
    ranked = _top_ranked_candidates(quantitative_analysis)
    if not ranked:
        return NewsCollectionResult(
            status="not_requested", source="NAVER API HUB news search",
            search_window_start=search_start, search_window_end=search_end,
            selected_etf_count=0, collected_article_count=0, article_limit=NEWS_ARTICLE_LIMIT,
            message="정량 적합점수가 산출된 ETF가 없어 뉴스 수집을 수행하지 않았습니다.",
        )

    source_collector = collector or NaverNewsCollector()
    per_etf: list[EtfNewsCollection] = []
    all_articles: list[tuple[int, EtfNewsCollection, NewsArticle]] = []
    for candidate in ranked:
        name = str(candidate["name"])
        ticker = str(candidate["ticker"])
        rank = int(candidate["score"]["rank"])
        try:
            articles = source_collector.collect(name, search_start, search_end)
        except NaverNewsCollectorError:
            logger.warning("analysis_news_stage_failed ticker=%s", ticker)
            raise
        mapped = EtfNewsCollection(
            ticker=ticker, name=name, quantitative_rank=rank, query=name,
            articles=[
                NewsArticle(
                    article_id=item.article_id, title=item.title, description=item.description,
                    original_link=item.original_link, link=item.link, publisher=item.publisher,
                    published_at=item.published_at,
                )
                for item in articles
            ],
        )
        per_etf.append(mapped)
        all_articles.extend((rank, mapped, article) for article in mapped.articles)

    all_articles.sort(key=lambda item: (item[0], -item[2].published_at.timestamp(), item[2].article_id))
    selected_keys = {
        (etf.ticker, article.article_id)
        for _, etf, article in all_articles[:NEWS_ARTICLE_LIMIT]
    }
    for item in per_etf:
        item.articles[:] = [
            article for article in item.articles
            if (item.ticker, article.article_id) in selected_keys
        ]
    collected_count = sum(len(item.articles) for item in per_etf)
    return NewsCollectionResult(
        status="available" if collected_count else "no_news",
        source="NAVER API HUB news search", search_window_start=search_start,
        search_window_end=search_end, selected_etf_count=len(ranked),
        collected_article_count=collected_count, article_limit=NEWS_ARTICLE_LIMIT,
        etfs=per_etf,
        message="최근 30일 내 뉴스 원천을 ETF별로 수집했습니다. 감성 분석은 수행하지 않았습니다.",
    )


def _top_ranked_candidates(quantitative_analysis: dict[str, object] | None) -> list[dict[str, object]]:
    if not quantitative_analysis:
        return []
    candidates = quantitative_analysis.get("candidates")
    if not isinstance(candidates, list):
        return []
    ranked = [
        candidate for candidate in candidates
        if isinstance(candidate, dict)
        and isinstance(candidate.get("score"), dict)
        and candidate["score"].get("status") == "calculated"
        and isinstance(candidate["score"].get("rank"), int)
        and isinstance(candidate.get("ticker"), str)
        and isinstance(candidate.get("name"), str)
    ]
    return sorted(ranked, key=lambda candidate: int(candidate["score"]["rank"]))[:NEWS_ETF_LIMIT]
