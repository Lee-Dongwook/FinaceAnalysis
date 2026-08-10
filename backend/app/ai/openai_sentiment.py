import json
from typing import Protocol

from app.core.config import Settings, settings
from app.models.sentiment import SentimentAssessment, StoredNewsArticle


class SentimentAnalyzerError(Exception):
    """Raised when a sentiment result cannot be safely produced."""


class SentimentAnalyzer(Protocol):
    def analyze(self, ticker: str, name: str, articles: list[StoredNewsArticle]) -> SentimentAssessment:
        """Return a source-grounded ETF sentiment assessment."""


class OpenAiSentimentAnalyzer:
    """OpenAI Responses API adapter with a strict, evidence-only JSON contract."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def analyze(self, ticker: str, name: str, articles: list[StoredNewsArticle]) -> SentimentAssessment:
        if not self.settings.openai_api_key or not self.settings.openai_sentiment_model:
            raise SentimentAnalyzerError("OpenAI sentiment settings are not configured.")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise SentimentAnalyzerError("OpenAI SDK is not installed.") from error
        payload = {
            "ticker": ticker,
            "etf_name": name,
            "articles": [
                {"article_id": article.article_id, "title": article.title,
                 "description": article.description or "", "publisher": article.publisher,
                 "published_at": article.published_at.isoformat()}
                for article in articles
            ],
        }
        try:
            response = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.openai_request_timeout_seconds).responses.create(
                model=self.settings.openai_sentiment_model,
                store=False,
                instructions=(
                    "Analyze only the supplied Korean ETF news. Do not give investment advice, forecast returns, "
                    "or create portfolio weights. Score sentiment from 0 (negative) to 100 (positive). "
                    "Set evidence_sufficient false if articles are unrelated or cannot support a conclusion. "
                    "Every evidence_article_id must be supplied in the input."
                ),
                input=json.dumps(payload, ensure_ascii=False),
                text={"format": {"type": "json_schema", "name": "etf_news_sentiment", "strict": True, "schema": _SCHEMA}},
            )
            result = json.loads(response.output_text)
        except Exception as error:
            raise SentimentAnalyzerError("OpenAI sentiment analysis failed.") from error
        return _parse_assessment(result)


def _parse_assessment(value: object) -> SentimentAssessment:
    if not isinstance(value, dict):
        raise SentimentAnalyzerError("OpenAI response is not a JSON object.")
    score = value.get("sentiment_score")
    fields = ("sentiment_rationale", "core_issues", "risk_factors", "keywords", "evidence_article_ids")
    if not isinstance(score, int) or not 0 <= score <= 100 or not isinstance(value.get("evidence_sufficient"), bool) or any(field not in value for field in fields):
        raise SentimentAnalyzerError("OpenAI response is missing or has invalid required fields.")
    lists = [value["core_issues"], value["risk_factors"], value["keywords"], value["evidence_article_ids"]]
    if not isinstance(value["sentiment_rationale"], str) or any(not isinstance(items, list) or not all(isinstance(item, str) for item in items) for items in lists):
        raise SentimentAnalyzerError("OpenAI response has invalid sentiment field types.")
    return SentimentAssessment(score, value["evidence_sufficient"], value["sentiment_rationale"].strip(),
        tuple(item.strip() for item in value["core_issues"] if item.strip()), tuple(item.strip() for item in value["risk_factors"] if item.strip()),
        tuple(item.strip() for item in value["keywords"] if item.strip()), tuple(item.strip() for item in value["evidence_article_ids"] if item.strip()))


_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "sentiment_score": {"type": "integer", "minimum": 0, "maximum": 100}, "evidence_sufficient": {"type": "boolean"},
        "sentiment_rationale": {"type": "string"}, "core_issues": {"type": "array", "items": {"type": "string"}},
        "risk_factors": {"type": "array", "items": {"type": "string"}}, "keywords": {"type": "array", "items": {"type": "string"}},
        "evidence_article_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sentiment_score", "evidence_sufficient", "sentiment_rationale", "core_issues", "risk_factors", "keywords", "evidence_article_ids"],
}
