from app.api.schemas.analysis import AnalysisRequest
from app.core.etf_cache import CachedEtfSnapshot
from app.models.etf import EtfSnapshot
from app.services.analysis_service import run_analysis


class StubCollector:
    def collect_latest(self) -> list[EtfSnapshot]:
        return [EtfSnapshot(
            ticker="069500", name="KODEX 200", market="ETF", close_price_krw=50_000,
            trade_volume=1_000, trade_value_krw=50_000_000, as_of_date="20260804",
            asset_types=frozenset({"equity"}), classification_source="keyword_fallback",
        )]


class EmptyCache:
    def load_if_current(self) -> None:
        return None

    def save(self, snapshots: list[EtfSnapshot]) -> CachedEtfSnapshot:
        return CachedEtfSnapshot(snapshots=snapshots, as_of_date="20260804", collected_at=__import__("datetime").datetime.now())

    def load_history_for_tickers(self, tickers: list[str], start_date: str, end_date: str) -> dict[str, list[EtfSnapshot]]:
        return {ticker: [] for ticker in tickers}

    def save_news_collection(self, collection: object) -> int:
        return 0


class CurrentCache:
    def __init__(self) -> None:
        self.snapshot = StubCollector().collect_latest()

    def load_if_current(self) -> CachedEtfSnapshot:
        return CachedEtfSnapshot(snapshots=self.snapshot, as_of_date="20260804", collected_at=__import__("datetime").datetime.now())

    def save(self, snapshots: list[EtfSnapshot]) -> CachedEtfSnapshot:
        raise AssertionError("Current cache must not be refreshed.")

    def load_history_for_tickers(self, tickers: list[str], start_date: str, end_date: str) -> dict[str, list[EtfSnapshot]]:
        return {ticker: [snapshot for snapshot in self.snapshot if snapshot.ticker == ticker] for ticker in tickers}

    def save_news_collection(self, collection: object) -> int:
        return 0


def test_analysis_returns_first_stage_candidates_with_news_collection_state() -> None:
    response = run_analysis(
        AnalysisRequest(
            investment_amount_krw=1_000_000, investment_period_months=12,
            risk_profile="moderate", max_loss_percent=20,
        ), collector=StubCollector(), cache=EmptyCache(),  # type: ignore[arg-type]
    )

    assert response.status == "partial"
    assert response.candidate_filtering is not None
    assert response.candidate_filtering.candidates[0].ticker == "069500"
    assert response.data_context is not None
    assert response.data_context.data_origin == "krx"
    assert response.news_collection is not None
    assert response.news_collection.status == "not_requested"


def test_analysis_uses_current_database_cache() -> None:
    response = run_analysis(
        AnalysisRequest(
            investment_amount_krw=1_000_000, investment_period_months=12,
            risk_profile="moderate", max_loss_percent=20,
        ), collector=StubCollector(), cache=CurrentCache(),  # type: ignore[arg-type]
    )

    assert response.data_context is not None
    assert response.data_context.data_origin == "database"
