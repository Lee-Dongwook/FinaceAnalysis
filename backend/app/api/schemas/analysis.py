from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    client_request_id: str | None = Field(default=None, min_length=1, max_length=100)
    investment_amount_krw: int = Field(ge=1_000_000, le=1_000_000_000)
    investment_period_months: int = Field(ge=1, le=60)
    quantitative_analysis_period_months: int = Field(default=12, ge=1, le=12)
    risk_profile: Literal["conservative", "moderate", "aggressive"]
    max_loss_percent: float = Field(ge=0, le=100)
    preferred_asset_types: list[str] | None = None
    theme_industry_keywords: list[str] | None = Field(default=None, max_length=5)
    cash_ratio_percent: float | None = Field(default=None, ge=0, le=100)

    @field_validator("theme_industry_keywords")
    @classmethod
    def normalize_theme_industry_keywords(cls, values: list[str] | None) -> list[str] | None:
        if not values:
            return None
        keywords: list[str] = []
        for value in values:
            keyword = value.strip()
            if not keyword:
                continue
            if len(keyword) > 50:
                raise ValueError("Each theme or industry keyword must be 50 characters or fewer.")
            if keyword not in keywords:
                keywords.append(keyword)
        return keywords or None


class AnalysisError(BaseModel):
    scope: str
    code: str
    message: str
    retryable: bool


class AnalysisEcho(BaseModel):
    received_conditions: AnalysisRequest
    message: str


class EtfCandidate(BaseModel):
    ticker: str
    name: str
    market: str | None = None
    asset_types: list[str]
    classification_source: Literal["krx", "keyword_fallback"]
    close_price_krw: int
    trade_volume: int | None = None
    trade_value_krw: int | None = None
    as_of_date: str
    affordable_units: int
    matched_preferred_asset_types: list[str] = Field(default_factory=list)
    matched_theme_industry_keywords: list[str] = Field(default_factory=list)


class CandidateFilteringResult(BaseModel):
    collected_count: int
    eligible_count: int
    excluded_count: int
    candidate_limit: int = 200
    rules_version: str
    candidates: list[EtfCandidate] = Field(default_factory=list)


class EtfDataContext(BaseModel):
    source: str
    retrieved_at: datetime
    as_of_date: str | None = None
    currency: Literal["KRW"] = "KRW"
    unit: str = "KRW, shares"
    data_origin: Literal["database", "krx"]
    cache_status: Literal["current", "refreshed"]


class NewsArticle(BaseModel):
    article_id: str
    title: str
    description: str | None = None
    original_link: str
    link: str | None = None
    publisher: str
    published_at: datetime


class EtfNewsCollection(BaseModel):
    ticker: str
    name: str
    quantitative_rank: int
    query: str
    articles: list[NewsArticle] = Field(default_factory=list)


class NewsCollectionResult(BaseModel):
    status: Literal["available", "no_news", "unavailable", "not_requested"]
    source: str
    search_window_start: datetime
    search_window_end: datetime
    selected_etf_count: int
    collected_article_count: int
    article_limit: int
    etfs: list[EtfNewsCollection] = Field(default_factory=list)
    stored_article_count: int | None = None
    stored_at: datetime | None = None
    message: str


class SentimentEtfResult(BaseModel):
    ticker: str
    name: str
    quantitative_rank: int
    article_count: int
    status: Literal["available", "excluded", "unavailable"]
    exclusion_reason: str | None = None
    sentiment_score: int | None = Field(default=None, ge=0, le=100)
    sentiment_rationale: str | None = None
    core_issues: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    evidence_article_ids: list[str] = Field(default_factory=list)


class SentimentAnalysisResult(BaseModel):
    status: Literal["available", "insufficient_evidence", "unavailable", "not_requested"]
    run_id: str | None = None
    source: str
    model: str | None = None
    minimum_articles: int
    maximum_parallel_requests: int
    analyzed_at: datetime | None = None
    eligible_tickers: list[str] = Field(default_factory=list)
    results: list[SentimentEtfResult] = Field(default_factory=list)


class NewsCandidateAnalysisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    additional_keywords: list[str] = Field(default_factory=list, max_length=10)


class ValidatedNewsArticleResponse(NewsArticle):
    relevance_score: float = Field(ge=0, le=1)


class NewsCandidateAnalysisResponse(BaseModel):
    status: Literal["available", "no_news", "analysis_unavailable"]
    ticker: str
    name: str
    search_keywords: list[str]
    search_window_start: datetime
    search_window_end: datetime
    relevance_threshold: float
    articles: list[ValidatedNewsArticleResponse] = Field(default_factory=list)
    sentiment: SentimentEtfResult | None = None


class PortfolioHolding(BaseModel):
    ticker: str
    name: str
    weight_percent: float
    target_amount_krw: int
    purchase_units: int
    purchase_amount_krw: int
    holding_period_months: int
    quantitative_score: float
    sentiment_score: int | None = None
    recommendation_rationale: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)


class PortfolioResult(BaseModel):
    status: Literal["available", "insufficient_candidates", "insufficient_sentiment"]
    investable_amount_krw: int
    cash_amount_krw: int
    unallocated_amount_krw: int
    holding_period_months: int
    holdings: list[PortfolioHolding] = Field(default_factory=list)
    summary: str
    warnings: list[str] = Field(default_factory=list)


class EtfConstituentItem(BaseModel):
    constituent_code: str
    constituent_name: str
    weight_percent: float = Field(gt=0, le=100)
    quantity: int | None = None
    evaluation_amount_krw: int | None = None
    current_price_krw: int | None = None
    price_change_krw: int | None = None


class EtfHoldingsResponse(BaseModel):
    status: Literal["available", "unsupported_provider", "source_unavailable"]
    ticker: str
    etf_name: str
    as_of_date: str | None = None
    collected_at: datetime | None = None
    source: str
    source_url: str | None = None
    data_origin: Literal["database", "official_site", "none"]
    cache_status: Literal["current", "refreshed", "unavailable"]
    source_record_count: int = 0
    excluded_record_count: int = 0
    constituents: list[EtfConstituentItem] = Field(default_factory=list)
    message: str


class AnalysisResponse(BaseModel):
    request_id: str
    status: Literal["completed", "partial", "failed"]
    analysis: AnalysisEcho | None = None
    data_context: EtfDataContext | None = None
    candidate_filtering: CandidateFilteringResult | None = None
    quantitative_analysis: dict[str, object] | None = None
    news_collection: NewsCollectionResult | None = None
    sentiment_analysis: SentimentAnalysisResult | None = None
    portfolio: PortfolioResult | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[AnalysisError] = Field(default_factory=list)
    disclaimer: str
