from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CollectedNewsArticle:
    """A source article only; it intentionally contains no summary or sentiment."""

    article_id: str
    title: str
    description: str | None
    original_link: str
    link: str | None
    publisher: str
    published_at: datetime
