from dataclasses import dataclass


WEIGHTS = {
    "conservative": {"return": 10, "volatility": 30, "mdd": 35, "sharpe": 10, "liquidity": 15},
    "moderate": {"return": 25, "volatility": 20, "mdd": 25, "sharpe": 20, "liquidity": 10},
    "aggressive": {"return": 40, "volatility": 10, "mdd": 15, "sharpe": 25, "liquidity": 10},
}


@dataclass(frozen=True)
class ScoreInput:
    ticker: str
    total_return_percent: float
    annualized_volatility_percent: float
    max_drawdown_percent: float
    sharpe_ratio: float
    average_trade_value_krw: float


@dataclass(frozen=True)
class ScoreResult:
    ticker: str
    total_score: float
    normalized_scores: dict[str, float]
    contributions: dict[str, float]


def score_candidates(inputs: list[ScoreInput], risk_profile: str) -> list[ScoreResult]:
    """Return deterministic 0-100 suitability scores using documented weights."""
    weights = WEIGHTS[risk_profile]
    if sum(weights.values()) != 100:
        raise ValueError("Quantitative score weights must total 100.")
    values = {
        "return": [item.total_return_percent for item in inputs],
        "volatility": [item.annualized_volatility_percent for item in inputs],
        "mdd": [abs(item.max_drawdown_percent) for item in inputs],
        "sharpe": [item.sharpe_ratio for item in inputs],
        "liquidity": [item.average_trade_value_krw for item in inputs],
    }
    directions = {"return": True, "volatility": False, "mdd": False, "sharpe": True, "liquidity": True}
    results: list[ScoreResult] = []
    for index, item in enumerate(inputs):
        normalized = {
            key: _normalize(values[key][index], values[key], directions[key])
            for key in values
        }
        contributions = {key: normalized[key] * weights[key] / 100 for key in normalized}
        results.append(ScoreResult(item.ticker, sum(contributions.values()), normalized, contributions))
    return sorted(results, key=lambda item: (-item.total_score, item.ticker))


def _normalize(value: float, population: list[float], higher_is_better: bool) -> float:
    minimum, maximum = min(population), max(population)
    if maximum == minimum:
        return 50.0
    raw = (value - minimum) / (maximum - minimum) * 100
    return raw if higher_is_better else 100 - raw
