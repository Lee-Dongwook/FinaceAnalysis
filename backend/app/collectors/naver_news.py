import hashlib
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings, settings
from app.models.news import CollectedNewsArticle


logger = logging.getLogger(__name__)
NAVER_NEWS_SEARCH_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"


class NaverNewsCollectorError(Exception):
    """Safe error raised when NAVER API HUB cannot provide news data."""


class NaverNewsConfigurationError(NaverNewsCollectorError):
    pass


class NaverNewsCollector:
    """Adapter for NAVER API HUB news search. It does not analyze article meaning."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def collect(self, query: str, published_from: datetime, published_to: datetime) -> list[CollectedNewsArticle]:
        if not self.settings.naver_api_key_id or not self.settings.naver_api_key:
            raise NaverNewsConfigurationError("NAVER API HUB credentials are not configured.")
        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.settings.naver_api_key_id,
            "X-NCP-APIGW-API-KEY": self.settings.naver_api_key,
        }
        params = {"query": query, "display": 100, "start": 1, "sort": "date", "format": "json"}
        try:
            with httpx.Client(timeout=self.settings.naver_news_request_timeout_seconds) as client:
                response = client.get(NAVER_NEWS_SEARCH_URL, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("naver_news_collection_failed query=%s error_type=%s", query, type(error).__name__)
            raise NaverNewsCollectorError("NAVER news collection failed.") from error

        items = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            raise NaverNewsCollectorError("NAVER news response does not contain article items.")
        articles = [
            article
            for item in items
            if isinstance(item, dict)
            and (article := self._normalize(item)) is not None
            and published_from <= article.published_at <= published_to
        ]
        logger.info("naver_news_collection_succeeded query=%s articles=%s", query, len(articles))
        return articles

    @staticmethod
    def _normalize(item: dict[str, Any]) -> CollectedNewsArticle | None:
        original_link = str(item.get("originallink") or item.get("link") or "").strip()
        published_at = NaverNewsCollector._parse_datetime(item.get("pubDate"))
        title = NaverNewsCollector._strip_html(item.get("title"))
        if not original_link or published_at is None or not title:
            return None
        description = NaverNewsCollector._strip_html(item.get("description")) or None
        publisher = urlparse(original_link).netloc or "unknown"
        article_id = hashlib.sha256(original_link.encode("utf-8")).hexdigest()[:20]
        return CollectedNewsArticle(article_id, title, description, original_link, str(item.get("link") or "").strip() or None, publisher, published_at)

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return parsed.astimezone(ZoneInfo("Asia/Seoul"))

    @staticmethod
    def _strip_html(value: object) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"<[^>]+>", "", unescape(value)).strip()
