from datetime import date

from app.core.etf_cache import SqliteEtfCache
from app.quantitative.first_stage_filter import CandidateMatch
from app.quantitative.metrics import PricePoint, calculate_metrics
from app.quantitative.scoring import WEIGHTS, ScoreInput, score_candidates


def _subtract_months(end: date, months: int) -> date:
    month = end.month - months
    year = end.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, min(end.day, 28))


def build_quantitative_analysis(
    candidates: tuple[CandidateMatch, ...],
    period_months: int,
    end_date_text: str,
    cache: SqliteEtfCache,
    weekly_sample_weekday: int | None,
    kofr_annual_rate_percent: float | None,
    risk_profile: str,
) -> dict[str, object]:
    end_date = date.fromisoformat(f"{end_date_text[:4]}-{end_date_text[4:6]}-{end_date_text[6:]}")
    requested_start = _subtract_months(end_date, period_months)
    history = cache.load_history_for_tickers(
        [candidate.snapshot.ticker for candidate in candidates],
        requested_start.strftime("%Y%m%d"), end_date_text,
    )
    rows: list[dict[str, object]] = []
    score_inputs: list[ScoreInput] = []
    for candidate in candidates:
        points = [
            PricePoint(date.fromisoformat(f"{item.as_of_date[:4]}-{item.as_of_date[4:6]}-{item.as_of_date[6:]}"), item.close_price_krw, item.trade_volume, item.trade_value_krw)
            for item in history[candidate.snapshot.ticker]
        ]
        metric = calculate_metrics(points, requested_start, end_date, weekly_sample_weekday, kofr_annual_rate_percent)
        row: dict[str, object] = {
            "ticker": candidate.snapshot.ticker, "name": candidate.snapshot.name,
            "total_return_percent": metric.total_return_percent,
            "annualized_volatility_percent": metric.annualized_volatility_percent,
            "max_drawdown_percent": metric.max_drawdown_percent,
            "sharpe_ratio": metric.sharpe_ratio,
            "average_trade_volume": metric.average_trade_volume,
            "average_trade_value_krw": metric.average_trade_value_krw,
            "actual_start_date": metric.actual_start_date.isoformat() if metric.actual_start_date else None,
            "end_date": metric.end_date.isoformat() if metric.end_date else None,
            "valid_daily_observations": metric.valid_daily_observations,
            "weekly_observations": metric.weekly_observations,
            "excluded_observations": metric.excluded_observations,
            "statuses": list(metric.statuses), "score": None,
        }
        rows.append(row)
        if None not in (metric.total_return_percent, metric.annualized_volatility_percent, metric.max_drawdown_percent, metric.sharpe_ratio, metric.average_trade_value_krw):
            score_inputs.append(ScoreInput(candidate.snapshot.ticker, metric.total_return_percent, metric.annualized_volatility_percent, metric.max_drawdown_percent, metric.sharpe_ratio, metric.average_trade_value_krw))
    scores = {score.ticker: score for score in score_candidates(score_inputs, risk_profile)}
    for rank, score in enumerate(scores.values(), start=1):
        row = next(row for row in rows if row["ticker"] == score.ticker)
        row["score"] = {"status": "calculated", "value": score.total_score, "rank": rank, "normalized_scores": score.normalized_scores, "contributions": score.contributions}
    rows.sort(key=lambda row: (row["score"] is None, -(row["score"] or {}).get("value", 0), str(row["ticker"])))
    return {
        "price_basis": "KRX daily raw closing price; adjusted price is unavailable",
        "requested_period_months": period_months,
        "requested_start_date": requested_start.isoformat(), "common_end_date": end_date.isoformat(),
        "weekly_sampling_policy": {"weekday": weekly_sample_weekday, "holiday_rule": "Friday or the latest trading day in the same week", "minimum_observations": 20, "status": "assumed"},
        "risk_free_rate": {"source": "KOFR", "annual_rate_percent": kofr_annual_rate_percent, "weekly_conversion": "annual_rate / 52", "status": "assumed"},
        "score_weights": _response_score_weights(),
        "candidates": rows,
    }


def _response_score_weights() -> dict[str, dict[str, int]]:
    """Expose the scoring source of truth with response field names."""
    response_key_by_metric = {"liquidity": "average_trade_value_krw"}
    profiles = tuple(WEIGHTS)
    return {
        response_key_by_metric.get(metric, metric): {
            profile: WEIGHTS[profile][metric] for profile in profiles
        }
        for metric in WEIGHTS[profiles[0]]
    }
