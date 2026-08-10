from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredNewsArticle:
    article_id: str
    title: str
    description: str | None
    publisher: str
    published_at: datetime


@dataclass(frozen=True)
class SentimentAssessment:
    sentiment_score: int
    evidence_sufficient: bool
    sentiment_rationale: str
    core_issues: tuple[str, ...]
    risk_factors: tuple[str, ...]
    keywords: tuple[str, ...]
    evidence_article_ids: tuple[str, ...]
