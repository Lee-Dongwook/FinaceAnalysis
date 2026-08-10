from app.api.schemas.analysis import AnalysisRequest
from app.models.etf import EtfSnapshot
from app.quantitative.first_stage_filter import filter_first_stage_candidates


def snapshot(ticker: str, price: int, assets: set[str], trade_value: int = 10_000) -> EtfSnapshot:
    return EtfSnapshot(
        ticker=ticker, name=ticker, market="ETF", close_price_krw=price,
        trade_volume=100, trade_value_krw=trade_value, as_of_date="20260804",
        asset_types=frozenset(assets), classification_source="krx",
    )


def request(**overrides: object) -> AnalysisRequest:
    values = {
        "investment_amount_krw": 1_000_000, "investment_period_months": 12,
        "risk_profile": "moderate", "max_loss_percent": 20,
        "preferred_asset_types": ["bond"], "cash_ratio_percent": 10,
    }
    values.update(overrides)
    return AnalysisRequest(**values)


def test_filter_excludes_restricted_and_unaffordable_etfs() -> None:
    result = filter_first_stage_candidates(
        [
            snapshot("BOND", 100_000, {"bond"}),
            snapshot("LEVERAGED", 50_000, {"restricted"}),
            snapshot("EXPENSIVE", 1_000_000, {"equity"}),
        ], request(),
    )

    assert [candidate.snapshot.ticker for candidate in result.candidates] == ["BOND"]
    assert {excluded.reason for excluded in result.excluded} == {
        "restricted_product", "investment_amount_insufficient",
    }


def test_filter_prioritizes_preferred_assets_and_limits_to_200() -> None:
    snapshots = [snapshot(f"E{i:03}", 10_000, {"equity"}, i) for i in range(201)]
    snapshots.append(snapshot("PREFERRED", 100_000, {"bond"}, 1))

    result = filter_first_stage_candidates(snapshots, request(cash_ratio_percent=0))

    assert len(result.candidates) == 200
    assert result.candidates[0].snapshot.ticker == "PREFERRED"
    assert {excluded.reason for excluded in result.excluded} == {"candidate_limit_exceeded"}


def test_filter_excludes_invalid_market_data() -> None:
    invalid = snapshot("INVALID", 10_000, {"equity"})
    invalid = EtfSnapshot(
        ticker=invalid.ticker, name=invalid.name, market=invalid.market, close_price_krw=0,
        trade_volume=invalid.trade_volume, trade_value_krw=invalid.trade_value_krw,
        as_of_date=invalid.as_of_date, asset_types=invalid.asset_types,
        classification_source=invalid.classification_source,
    )

    result = filter_first_stage_candidates([invalid], request())

    assert result.candidates == ()
    assert result.excluded[0].reason == "invalid_market_data"


def test_filter_applies_optional_theme_industry_keywords() -> None:
    semiconductor = EtfSnapshot(
        ticker="SEMICON", name="반도체 ETF", market="ETF", close_price_krw=10_000,
        trade_volume=100, trade_value_krw=10_000, as_of_date="20260804",
        asset_types=frozenset({"equity"}), classification_source="krx",
        raw_classification="KRX 반도체 지수",
    )
    bond = snapshot("BOND", 10_000, {"bond"})

    result = filter_first_stage_candidates(
        [semiconductor, bond], request(
            preferred_asset_types=[], theme_industry_keywords=["반도체"]
        )
    )

    assert [candidate.snapshot.ticker for candidate in result.candidates] == ["SEMICON"]
    assert result.candidates[0].matched_theme_industry_keywords == ("반도체",)
    assert {excluded.reason for excluded in result.excluded} == {"theme_industry_keyword_mismatch"}
