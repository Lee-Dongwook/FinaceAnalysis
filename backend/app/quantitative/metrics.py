import math
import statistics
from dataclasses import dataclass
from datetime import date


MIN_WEEKLY_OBSERVATIONS = 20


@dataclass(frozen=True)
class PricePoint:
    trading_date: date
    close_price_krw: float
    trade_volume: int | None
    trade_value_krw: int | None


@dataclass(frozen=True)
class MetricCalculation:
    total_return_percent: float | None
    annualized_volatility_percent: float | None
    max_drawdown_percent: float | None
    sharpe_ratio: float | None
    average_trade_volume: float | None
    average_trade_value_krw: float | None
    actual_start_date: date | None
    end_date: date | None
    valid_daily_observations: int
    weekly_observations: int
    excluded_observations: int
    statuses: tuple[str, ...]


def calculate_metrics(
    points: list[PricePoint],
    requested_start_date: date,
    end_date: date,
    weekly_sample_weekday: int | None,
    kofr_annual_rate_percent: float | None,
) -> MetricCalculation:
    """Calculate deterministic ETF metrics from KRX daily closing-price records."""
    statuses: list[str] = []
    unique_points: dict[date, PricePoint] = {}
    excluded = 0
    for point in points:
        if point.trading_date < requested_start_date or point.trading_date > end_date:
            continue
        if point.close_price_krw <= 0:
            excluded += 1
            continue
        if point.trading_date in unique_points:
            excluded += 1
            continue
        unique_points[point.trading_date] = point
    valid_points = [unique_points[key] for key in sorted(unique_points)]
    if len(valid_points) < 2:
        statuses.append("insufficient_history")
        return MetricCalculation(
            None, None, None, None, None, None,
            valid_points[0].trading_date if valid_points else None,
            valid_points[-1].trading_date if valid_points else None,
            len(valid_points), 0, excluded, tuple(statuses),
        )
    if valid_points[0].trading_date > requested_start_date:
        statuses.append("available_history_shortened")

    total_return = (valid_points[-1].close_price_krw / valid_points[0].close_price_krw - 1) * 100
    peak = valid_points[0].close_price_krw
    max_drawdown = 0.0
    for point in valid_points:
        peak = max(peak, point.close_price_krw)
        max_drawdown = min(max_drawdown, (point.close_price_krw / peak - 1) * 100)
    volumes = [point.trade_volume for point in valid_points if point.trade_volume is not None]
    values = [point.trade_value_krw for point in valid_points if point.trade_value_krw is not None]
    average_volume = statistics.fmean(volumes) if volumes else None
    average_value = statistics.fmean(values) if values else None

    volatility: float | None = None
    sharpe: float | None = None
    weekly_points = _weekly_points(valid_points, weekly_sample_weekday)
    if weekly_sample_weekday is None:
        statuses.append("weekly_sampling_policy_pending")
    elif len(weekly_points) < MIN_WEEKLY_OBSERVATIONS:
        statuses.append("insufficient_weekly_observations")
    else:
        weekly_returns = [
            weekly_points[index].close_price_krw / weekly_points[index - 1].close_price_krw - 1
            for index in range(1, len(weekly_points))
        ]
        standard_deviation = statistics.stdev(weekly_returns)
        volatility = standard_deviation * math.sqrt(52) * 100
        if standard_deviation == 0:
            statuses.append("zero_denominator")
        elif kofr_annual_rate_percent is None:
            statuses.append("kofr_rate_pending")
        else:
            weekly_risk_free_rate = (kofr_annual_rate_percent / 100) / 52
            sharpe = (
                statistics.fmean(weekly_return - weekly_risk_free_rate for weekly_return in weekly_returns)
                / standard_deviation
                * math.sqrt(52)
            )
    return MetricCalculation(
        total_return, volatility, max_drawdown, sharpe, average_volume, average_value,
        valid_points[0].trading_date, valid_points[-1].trading_date,
        len(valid_points), len(weekly_points), excluded, tuple(statuses),
    )


def _weekly_points(points: list[PricePoint], weekday: int | None) -> list[PricePoint]:
    if weekday is None:
        return []
    selected: dict[tuple[int, int], PricePoint] = {}
    for point in points:
        if point.trading_date.weekday() > weekday:
            continue
        week_key = point.trading_date.isocalendar()[:2]
        selected[week_key] = point
    return [selected[key] for key in sorted(selected)]
