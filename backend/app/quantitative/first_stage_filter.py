from dataclasses import dataclass

from app.api.schemas.analysis import AnalysisRequest
from app.models.etf import EtfSnapshot

CANDIDATE_LIMIT = 200
RULES_VERSION = "first-stage-v3"
RISK_ALLOWED_ASSETS = {
    "conservative": frozenset({"bond", "cash"}),
    "moderate": frozenset({"bond", "cash", "equity", "dividend"}),
    "aggressive": frozenset({"equity", "dividend"}),
}


@dataclass(frozen=True)
class ExcludedEtf:
    ticker: str
    reason: str


@dataclass(frozen=True)
class CandidateMatch:
    snapshot: EtfSnapshot
    affordable_units: int
    matched_preferred_assets: tuple[str, ...]
    matched_theme_industry_keywords: tuple[str, ...]


@dataclass(frozen=True)
class FirstStageFilterResult:
    candidates: tuple[CandidateMatch, ...]
    excluded: tuple[ExcludedEtf, ...]
    collected_count: int
    eligible_count: int


def filter_first_stage_candidates(
    snapshots: list[EtfSnapshot], request: AnalysisRequest
) -> FirstStageFilterResult:
    investable_amount = int(
        request.investment_amount_krw * (1 - (request.cash_ratio_percent or 0) / 100)
    )
    preferred_assets = set(request.preferred_asset_types or [])
    theme_industry_keywords = tuple(request.theme_industry_keywords or [])
    allowed_assets = RISK_ALLOWED_ASSETS[request.risk_profile]
    eligible: list[CandidateMatch] = []
    excluded: list[ExcludedEtf] = []

    for snapshot in snapshots:
        if (
            not snapshot.ticker.strip()
            or not snapshot.name.strip()
            or not snapshot.as_of_date.strip()
            or snapshot.close_price_krw <= 0
        ):
            excluded.append(ExcludedEtf(snapshot.ticker, "invalid_market_data"))
            continue
        if "restricted" in snapshot.asset_types:
            excluded.append(ExcludedEtf(snapshot.ticker, "restricted_product"))
            continue
        if not snapshot.asset_types.intersection(allowed_assets):
            excluded.append(ExcludedEtf(snapshot.ticker, "risk_profile_mismatch"))
            continue
        affordable_units = investable_amount // snapshot.close_price_krw
        if affordable_units < 1:
            excluded.append(ExcludedEtf(snapshot.ticker, "investment_amount_insufficient"))
            continue
        matched = tuple(sorted(snapshot.asset_types.intersection(preferred_assets)))
        matched_theme_industry_keywords = _matched_theme_industry_keywords(
            snapshot, theme_industry_keywords
        )
        if theme_industry_keywords and not matched_theme_industry_keywords:
            excluded.append(ExcludedEtf(snapshot.ticker, "theme_industry_keyword_mismatch"))
            continue
        eligible.append(
            CandidateMatch(
                snapshot, affordable_units, matched, matched_theme_industry_keywords
            )
        )

    ranked_candidates = sorted(
        eligible,
        key=lambda candidate: (
            -len(candidate.matched_theme_industry_keywords),
            -len(candidate.matched_preferred_assets),
            -candidate.affordable_units,
            -(candidate.snapshot.trade_value_krw or 0),
            candidate.snapshot.ticker,
        ),
    )
    candidates = tuple(ranked_candidates[:CANDIDATE_LIMIT])
    excluded.extend(
        ExcludedEtf(candidate.snapshot.ticker, "candidate_limit_exceeded")
        for candidate in ranked_candidates[CANDIDATE_LIMIT:]
    )
    return FirstStageFilterResult(
        candidates=candidates,
        excluded=tuple(excluded),
        collected_count=len(snapshots),
        eligible_count=len(eligible),
    )


def _matched_theme_industry_keywords(
    snapshot: EtfSnapshot, keywords: tuple[str, ...]
) -> tuple[str, ...]:
    searchable_text = f"{snapshot.name} {snapshot.raw_classification or ''}".casefold()
    return tuple(keyword for keyword in keywords if keyword.casefold() in searchable_text)
