from datetime import date, timedelta

from app.quantitative.metrics import PricePoint, calculate_metrics
from app.quantitative.scoring import ScoreInput, score_candidates


def test_metrics_calculate_mdd_and_weekly_values_from_fixed_data() -> None:
    points = []
    value = 100.0
    for week in range(30):
        value *= 1.01 if week % 2 == 0 else 0.995
        points.append(PricePoint(date(2026, 1, 2) + timedelta(days=week * 7), value, 1000, 1_000_000))
    result = calculate_metrics(points, points[0].trading_date, points[-1].trading_date, 4, 3.0)
    assert result.total_return_percent is not None
    assert result.annualized_volatility_percent is not None
    assert result.sharpe_ratio is not None
    assert result.average_trade_value_krw == 1_000_000


def test_scoring_returns_fifty_when_all_values_match() -> None:
    scores = score_candidates([
        ScoreInput("A", 1, 2, -3, 4, 5), ScoreInput("B", 1, 2, -3, 4, 5)
    ], "moderate")
    assert all(score.total_score == 50 for score in scores)


def test_scoring_uses_trade_value_and_returns_descending_score_order() -> None:
    scores = score_candidates([
        ScoreInput("LOW", 1, 2, -3, 4, 100), ScoreInput("HIGH", 1, 2, -3, 4, 1_000)
    ], "moderate")
    assert scores[0].ticker == "HIGH"
