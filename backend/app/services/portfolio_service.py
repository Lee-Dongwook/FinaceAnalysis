from app.api.schemas.analysis import AnalysisRequest, PortfolioHolding, PortfolioResult, SentimentAnalysisResult
from app.quantitative.first_stage_filter import CandidateMatch

MIN_HOLDINGS, MAX_HOLDINGS, MIN_WEIGHT, MAX_WEIGHT = 3, 8, 5.0, 30.0


def build_portfolio(request: AnalysisRequest, candidates: tuple[CandidateMatch, ...], quantitative: dict[str, object] | None, sentiment: SentimentAnalysisResult | None) -> PortfolioResult:
    investable = int(request.investment_amount_krw * (1 - (request.cash_ratio_percent or 0) / 100))
    cash = request.investment_amount_krw - investable
    score_rows = {str(row["ticker"]): row for row in (quantitative or {}).get("candidates", []) if isinstance(row, dict) and isinstance(row.get("score"), dict) and row["score"].get("status") == "calculated"}
    sentiment_rows = {row.ticker: row for row in (sentiment.results if sentiment else []) if row.status == "available"}
    eligible = [item for item in candidates if item.snapshot.ticker in score_rows and item.snapshot.ticker in sentiment_rows]
    eligible.sort(key=lambda item: -float(score_rows[item.snapshot.ticker]["score"]["value"]))
    if len(eligible) < MIN_HOLDINGS:
        status = "insufficient_sentiment" if len(score_rows) >= MIN_HOLDINGS else "insufficient_candidates"
        return PortfolioResult(status=status, investable_amount_krw=investable, cash_amount_krw=cash, unallocated_amount_krw=investable, holding_period_months=request.investment_period_months, summary="유효한 정량·감성 근거를 모두 갖춘 ETF가 3개 미만입니다.", warnings=["포트폴리오를 구성하지 않았습니다."])
    selected = eligible[:MAX_HOLDINGS]
    scores = [float(score_rows[item.snapshot.ticker]["score"]["value"]) for item in selected]
    weights = _bounded_weights(scores)
    holdings: list[PortfolioHolding] = []
    spent = 0
    for item, weight, score in zip(selected, weights, scores):
        target = round(investable * weight / 100)
        units = target // item.snapshot.close_price_krw
        amount = units * item.snapshot.close_price_krw
        spent += amount
        sentiment_row = sentiment_rows[item.snapshot.ticker]
        holdings.append(PortfolioHolding(ticker=item.snapshot.ticker, name=item.snapshot.name, weight_percent=weight, target_amount_krw=target, purchase_units=units, purchase_amount_krw=amount, holding_period_months=request.investment_period_months, quantitative_score=score, sentiment_score=sentiment_row.sentiment_score, recommendation_rationale=[f"정량 적합점수 {score:.1f}", *sentiment_row.core_issues[:2]], risk_factors=sentiment_row.risk_factors[:3]))
    return PortfolioResult(status="available", investable_amount_krw=investable, cash_amount_krw=cash, unallocated_amount_krw=investable-spent, holding_period_months=request.investment_period_months, holdings=holdings, summary=f"투자 가능 금액 {investable:,}원 내에서 정량 점수와 검증된 뉴스 근거를 함께 확인한 {len(holdings)}개 ETF 정보 제공 구성입니다.", warnings=["뉴스 감성은 정량 점수에 가산하지 않고 근거·위험 확인에만 사용했습니다."])


def _bounded_weights(scores: list[float]) -> list[float]:
    raw = [score / sum(scores) * 100 for score in scores]
    weights = [min(MAX_WEIGHT, max(MIN_WEIGHT, value)) for value in raw]
    for _ in range(20):
        diff = 100 - sum(weights)
        if abs(diff) < .01: break
        adjustable = [index for index, value in enumerate(weights) if (diff > 0 and value < MAX_WEIGHT) or (diff < 0 and value > MIN_WEIGHT)]
        if not adjustable: break
        step = diff / len(adjustable)
        for index in adjustable: weights[index] = min(MAX_WEIGHT, max(MIN_WEIGHT, weights[index] + step))
    return [round(value, 2) for value in weights]
