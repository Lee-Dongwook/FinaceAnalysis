import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models.news import CollectedNewsArticle


@dataclass(frozen=True)
class ValidatedNewsArticle:
    article: CollectedNewsArticle
    relevance_score: float


def validate_news_articles(articles: list[CollectedNewsArticle], keywords: list[str], start: datetime, end: datetime, threshold: float) -> list[ValidatedNewsArticle]:
    """Keep only in-window, source-valid, deduplicated and ETF-relevant articles."""
    period_valid = [article for article in articles if start <= article.published_at <= end and article.publisher != "unknown" and article.original_link.startswith(("http://", "https://"))]
    unique = _deduplicate(period_valid)
    profile = " ".join(keywords)
    documents = [profile, *[f"{item.title} {item.description or ''}" for item in unique]]
    scores = _tfidf_cosines(documents)
    return [ValidatedNewsArticle(article, score) for article, score in zip(unique, scores) if score >= threshold]


def _deduplicate(articles: list[CollectedNewsArticle]) -> list[CollectedNewsArticle]:
    selected: list[CollectedNewsArticle] = []
    seen_urls: set[str] = set()
    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        normalized_url = _normalized_url(article.original_link)
        body = article.description or ""
        if normalized_url in seen_urls or any(_cosine(article.title, item.title) >= .92 and _cosine(body, item.description or "") >= .88 for item in selected):
            continue
        seen_urls.add(normalized_url)
        selected.append(article)
    return selected


def _normalized_url(value: str) -> str:
    parts = urlsplit(value)
    query = [(key, item) for key, item in parse_qsl(parts.query) if not key.lower().startswith(("utm_", "fbclid", "gclid"))]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def _tokens(value: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣]{2,}", value.casefold())


def _tfidf_cosines(documents: list[str]) -> list[float]:
    counts = [Counter(_tokens(document)) for document in documents]
    document_frequency = Counter(token for count in counts for token in count)
    total = len(counts)
    def vector(count: Counter[str]) -> dict[str, float]:
        return {token: frequency * (math.log((1 + total) / (1 + document_frequency[token])) + 1) for token, frequency in count.items()}
    profile = vector(counts[0])
    return [_vector_cosine(profile, vector(count)) for count in counts[1:]]


def _cosine(left: str, right: str) -> float:
    return _vector_cosine(Counter(_tokens(left)), Counter(_tokens(right)))


def _vector_cosine(left: dict[str, float] | Counter[str], right: dict[str, float] | Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(token, 0.0) for token, value in left.items())
    return dot / math.sqrt(sum(value * value for value in left.values()) * sum(value * value for value in right.values()))
