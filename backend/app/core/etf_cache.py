import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

from app.models.etf import EtfSnapshot
from app.models.holdings import EtfConstituent, EtfConstituentSnapshot
from app.models.sentiment import StoredNewsArticle

if TYPE_CHECKING:
    from app.api.schemas.analysis import NewsCollectionResult, SentimentAnalysisResult


KRX_SOURCE = "KRX Open API ETF daily trading information"


@dataclass(frozen=True)
class CachedEtfSnapshot:
    snapshots: list[EtfSnapshot]
    as_of_date: str
    collected_at: datetime


class SqliteEtfCache:
    """Operational cache for KRX ETF reference and daily trading data only."""

    def __init__(self, database_path: str) -> None:
        path = Path(database_path)
        self.path = path if path.is_absolute() else Path(__file__).resolve().parents[3] / path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS etf_daily_snapshots (
                    base_date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    name TEXT NOT NULL,
                    market TEXT,
                    manager TEXT,
                    listing_date TEXT,
                    listing_status TEXT,
                    close_price_krw INTEGER NOT NULL,
                    previous_close_change_krw INTEGER,
                    fluctuation_rate REAL,
                    nav REAL,
                    open_price_krw INTEGER,
                    high_price_krw INTEGER,
                    low_price_krw INTEGER,
                    trade_volume INTEGER,
                    trade_value_krw INTEGER,
                    market_cap_krw INTEGER,
                    net_assets_krw INTEGER,
                    listed_shares INTEGER,
                    index_name TEXT,
                    index_close REAL,
                    index_previous_change REAL,
                    index_fluctuation_rate REAL,
                    asset_types_json TEXT NOT NULL,
                    classification_source TEXT NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'KRW',
                    source TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    PRIMARY KEY (base_date, ticker)
                );
                CREATE INDEX IF NOT EXISTS idx_etf_daily_snapshots_base_date
                    ON etf_daily_snapshots (base_date);
                CREATE TABLE IF NOT EXISTS etf_collection_runs (
                    sync_date TEXT PRIMARY KEY,
                    as_of_date TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS news_articles (
                    article_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    original_link TEXT NOT NULL,
                    link TEXT,
                    publisher TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    first_collected_at TEXT NOT NULL,
                    last_collected_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS etf_news_matches (
                    ticker TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    etf_name TEXT NOT NULL,
                    query TEXT NOT NULL,
                    quantitative_rank INTEGER NOT NULL,
                    search_window_start TEXT NOT NULL,
                    search_window_end TEXT NOT NULL,
                    first_collected_at TEXT NOT NULL,
                    last_collected_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, article_id),
                    FOREIGN KEY (article_id) REFERENCES news_articles(article_id)
                );
                CREATE INDEX IF NOT EXISTS idx_etf_news_matches_ticker
                    ON etf_news_matches (ticker);
                CREATE INDEX IF NOT EXISTS idx_news_articles_published_at
                    ON news_articles (published_at);
                CREATE TABLE IF NOT EXISTS news_collection_runs (
                    collection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    search_window_start TEXT NOT NULL,
                    search_window_end TEXT NOT NULL,
                    selected_etf_count INTEGER NOT NULL,
                    collected_article_count INTEGER NOT NULL,
                    stored_article_count INTEGER NOT NULL,
                    completed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sentiment_analysis_runs (
                    run_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    model TEXT,
                    minimum_articles INTEGER NOT NULL,
                    maximum_parallel_requests INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    eligible_etf_count INTEGER NOT NULL,
                    analyzed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS etf_sentiment_analyses (
                    run_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    name TEXT NOT NULL,
                    quantitative_rank INTEGER NOT NULL,
                    article_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    exclusion_reason TEXT,
                    sentiment_score INTEGER,
                    sentiment_rationale TEXT,
                    core_issues_json TEXT NOT NULL,
                    risk_factors_json TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    evidence_article_ids_json TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, ticker),
                    FOREIGN KEY (run_id) REFERENCES sentiment_analysis_runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS idx_etf_sentiment_analyses_ticker
                    ON etf_sentiment_analyses (ticker);
                CREATE TABLE IF NOT EXISTS etf_constituent_snapshots (
                    etf_ticker TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    constituent_code TEXT NOT NULL,
                    constituent_name TEXT NOT NULL,
                    weight_percent REAL NOT NULL,
                    quantity INTEGER,
                    evaluation_amount_krw INTEGER,
                    current_price_krw INTEGER,
                    price_change_krw INTEGER,
                    source TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    PRIMARY KEY (etf_ticker, as_of_date, constituent_code)
                );
                CREATE INDEX IF NOT EXISTS idx_etf_constituent_snapshots_ticker_date
                    ON etf_constituent_snapshots (etf_ticker, as_of_date);
                CREATE TABLE IF NOT EXISTS etf_constituent_collection_state (
                    ticker TEXT PRIMARY KEY,
                    etf_name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    product_id TEXT,
                    as_of_date TEXT,
                    source_url TEXT,
                    source_record_count INTEGER NOT NULL DEFAULT 0,
                    excluded_record_count INTEGER NOT NULL DEFAULT 0,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    message TEXT,
                    collected_at TEXT NOT NULL
                );
                """
            )
            existing_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(etf_daily_snapshots)")
            }
            for column_name in ("manager", "listing_date", "listing_status"):
                if column_name not in existing_columns:
                    connection.execute(f"ALTER TABLE etf_daily_snapshots ADD COLUMN {column_name} TEXT")

    def load_constituents_collected_today(self, ticker: str) -> EtfConstituentSnapshot | None:
        """Load the latest successful constituent collection if it was refreshed today in KST."""
        with closing(self._connect()) as connection:
            state = connection.execute(
                """
                SELECT * FROM etf_constituent_collection_state
                WHERE ticker = ? AND status = 'available' AND substr(collected_at, 1, 10) = ?
                """,
                (ticker, self._today_kst()),
            ).fetchone()
            if state is None or state["as_of_date"] is None:
                return None
            rows = connection.execute(
                """
                SELECT * FROM etf_constituent_snapshots
                WHERE etf_ticker = ? AND as_of_date = ?
                ORDER BY weight_percent DESC, constituent_name
                """,
                (ticker, state["as_of_date"]),
            ).fetchall()
        if not rows:
            return None
        return EtfConstituentSnapshot(
            ticker=ticker,
            etf_name=state["etf_name"],
            provider=state["provider"],
            product_id=state["product_id"] or "",
            as_of_date=state["as_of_date"],
            source_url=state["source_url"] or "",
            collected_at=datetime.fromisoformat(state["collected_at"]),
            source_record_count=state["source_record_count"],
            excluded_record_count=state["excluded_record_count"],
            constituents=[self._row_to_constituent(row) for row in rows],
        )

    def save_constituent_snapshot(self, snapshot: EtfConstituentSnapshot) -> None:
        """Persist one provider-attributed constituent snapshot and its collection metadata."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM etf_constituent_snapshots WHERE etf_ticker = ? AND as_of_date = ?",
                (snapshot.ticker, snapshot.as_of_date),
            )
            connection.executemany(
                """
                INSERT INTO etf_constituent_snapshots (
                    etf_ticker, as_of_date, constituent_code, constituent_name, weight_percent,
                    quantity, evaluation_amount_krw, current_price_krw, price_change_krw,
                    source, source_url, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot.ticker, snapshot.as_of_date, item.constituent_code,
                        item.constituent_name, item.weight_percent, item.quantity,
                        item.evaluation_amount_krw, item.current_price_krw,
                        item.price_change_krw, snapshot.provider, snapshot.source_url,
                        snapshot.collected_at.isoformat(),
                    )
                    for item in snapshot.constituents
                ],
            )
            connection.execute(
                """
                INSERT INTO etf_constituent_collection_state (
                    ticker, etf_name, provider, product_id, as_of_date, source_url,
                    source_record_count, excluded_record_count, record_count, status, message, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'available', NULL, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    etf_name=excluded.etf_name, provider=excluded.provider, product_id=excluded.product_id,
                    as_of_date=excluded.as_of_date, source_url=excluded.source_url,
                    source_record_count=excluded.source_record_count,
                    excluded_record_count=excluded.excluded_record_count, record_count=excluded.record_count,
                    status='available', message=NULL, collected_at=excluded.collected_at
                """,
                (
                    snapshot.ticker, snapshot.etf_name, snapshot.provider, snapshot.product_id,
                    snapshot.as_of_date, snapshot.source_url, snapshot.source_record_count,
                    snapshot.excluded_record_count, len(snapshot.constituents), snapshot.collected_at.isoformat(),
                ),
            )

    def save_constituent_collection_failure(
        self, ticker: str, etf_name: str, status: str, message: str
    ) -> None:
        collected_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO etf_constituent_collection_state (
                    ticker, etf_name, provider, status, message, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    etf_name=excluded.etf_name, provider=excluded.provider, status=excluded.status,
                    message=excluded.message, collected_at=excluded.collected_at
                """,
                (ticker, etf_name, "Samsung Asset Management KODEX official constituent PDF", status, message, collected_at),
            )

    def save_news_collection(self, collection: "NewsCollectionResult") -> int:
        """Persist source articles and ETF matches for a later, separate sentiment stage."""
        collected_at = datetime.now(ZoneInfo("Asia/Seoul"))
        stored_matches = 0
        with closing(self._connect()) as connection, connection:
            for etf in collection.etfs:
                for article in etf.articles:
                    connection.execute(
                        """
                        INSERT INTO news_articles (
                            article_id, title, description, original_link, link, publisher,
                            published_at, source, first_collected_at, last_collected_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(article_id) DO UPDATE SET
                            title=excluded.title, description=excluded.description,
                            original_link=excluded.original_link, link=excluded.link,
                            publisher=excluded.publisher, published_at=excluded.published_at,
                            source=excluded.source, last_collected_at=excluded.last_collected_at
                        """,
                        (
                            article.article_id, article.title, article.description,
                            article.original_link, article.link, article.publisher,
                            article.published_at.isoformat(), collection.source,
                            collected_at.isoformat(), collected_at.isoformat(),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO etf_news_matches (
                            ticker, article_id, etf_name, query, quantitative_rank,
                            search_window_start, search_window_end, first_collected_at, last_collected_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(ticker, article_id) DO UPDATE SET
                            etf_name=excluded.etf_name, query=excluded.query,
                            quantitative_rank=excluded.quantitative_rank,
                            search_window_start=excluded.search_window_start,
                            search_window_end=excluded.search_window_end,
                            last_collected_at=excluded.last_collected_at
                        """,
                        (
                            etf.ticker, article.article_id, etf.name, etf.query,
                            etf.quantitative_rank, collection.search_window_start.isoformat(),
                            collection.search_window_end.isoformat(), collected_at.isoformat(),
                            collected_at.isoformat(),
                        ),
                    )
                    stored_matches += 1
            connection.execute(
                """
                INSERT INTO news_collection_runs (
                    source, search_window_start, search_window_end, selected_etf_count,
                    collected_article_count, stored_article_count, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    collection.source, collection.search_window_start.isoformat(),
                    collection.search_window_end.isoformat(), collection.selected_etf_count,
                    collection.collected_article_count, stored_matches, collected_at.isoformat(),
                ),
            )
        collection.stored_at = collected_at
        return stored_matches

    def load_news_for_collection(self, collected_at: datetime) -> dict[str, list[StoredNewsArticle]]:
        """Load the exact ETF/news rows persisted by one collection operation."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT m.ticker, a.article_id, a.title, a.description, a.publisher, a.published_at
                FROM etf_news_matches m
                JOIN news_articles a ON a.article_id = m.article_id
                WHERE m.last_collected_at = ?
                ORDER BY m.ticker, a.published_at DESC, a.article_id
                """,
                (collected_at.isoformat(),),
            ).fetchall()
        grouped: dict[str, list[StoredNewsArticle]] = {}
        for row in rows:
            grouped.setdefault(row["ticker"], []).append(
                StoredNewsArticle(
                    article_id=row["article_id"], title=row["title"], description=row["description"],
                    publisher=row["publisher"], published_at=datetime.fromisoformat(row["published_at"]),
                )
            )
        return grouped

    def save_sentiment_analysis(self, analysis: "SentimentAnalysisResult") -> None:
        if analysis.run_id is None or analysis.analyzed_at is None:
            raise ValueError("Sentiment analysis requires a run identifier and timestamp.")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO sentiment_analysis_runs (
                    run_id, source, model, minimum_articles, maximum_parallel_requests,
                    status, eligible_etf_count, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (analysis.run_id, analysis.source, analysis.model, analysis.minimum_articles,
                 analysis.maximum_parallel_requests, analysis.status, len(analysis.eligible_tickers),
                 analysis.analyzed_at.isoformat()),
            )
            connection.executemany(
                """
                INSERT INTO etf_sentiment_analyses (
                    run_id, ticker, name, quantitative_rank, article_count, status, exclusion_reason,
                    sentiment_score, sentiment_rationale, core_issues_json, risk_factors_json,
                    keywords_json, evidence_article_ids_json, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (analysis.run_id, item.ticker, item.name, item.quantitative_rank, item.article_count,
                     item.status, item.exclusion_reason, item.sentiment_score, item.sentiment_rationale,
                     json.dumps(item.core_issues, ensure_ascii=False), json.dumps(item.risk_factors, ensure_ascii=False),
                     json.dumps(item.keywords, ensure_ascii=False), json.dumps(item.evidence_article_ids),
                     analysis.analyzed_at.isoformat())
                    for item in analysis.results
                ],
            )

    @staticmethod
    def latest_weekday_date(reference_date: date | None = None) -> date:
        """Return the most recent weekday in Korea for a daily-market cache check."""
        current_date = reference_date or datetime.now(ZoneInfo("Asia/Seoul")).date()
        while current_date.weekday() >= 5:
            current_date -= timedelta(days=1)
        return current_date

    @classmethod
    def _today_kst(cls) -> str:
        return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()

    def load_if_current(self, reference_date: date | None = None) -> CachedEtfSnapshot | None:
        """Load the latest weekday's ETF snapshot, including on weekends.

        Example: a Saturday 2026-08-08 request expects Friday 2026-08-07 data.
        KRX holidays are handled by the collector when the expected weekday is unavailable.
        """
        expected_base_date = self.latest_weekday_date(reference_date).strftime("%Y%m%d")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM etf_daily_snapshots WHERE base_date = ? ORDER BY ticker",
                (expected_base_date,),
            ).fetchall()
        if not rows:
            return None
        return CachedEtfSnapshot(
            snapshots=[self._row_to_snapshot(row) for row in rows],
            as_of_date=expected_base_date,
            collected_at=max(datetime.fromisoformat(row["collected_at"]) for row in rows),
        )

    def load_current_ticker(self, ticker: str) -> EtfSnapshot | None:
        current = self.load_if_current()
        if current is None:
            return None
        return next((snapshot for snapshot in current.snapshots if snapshot.ticker == ticker), None)

    @staticmethod
    def _row_to_constituent(row: sqlite3.Row) -> EtfConstituent:
        return EtfConstituent(
            constituent_code=row["constituent_code"], constituent_name=row["constituent_name"],
            weight_percent=row["weight_percent"], quantity=row["quantity"],
            evaluation_amount_krw=row["evaluation_amount_krw"],
            current_price_krw=row["current_price_krw"], price_change_krw=row["price_change_krw"],
        )

    def save(self, snapshots: list[EtfSnapshot]) -> CachedEtfSnapshot:
        if not snapshots:
            raise ValueError("At least one ETF snapshot is required.")
        as_of_date = max(snapshot.as_of_date for snapshot in snapshots)
        collected_at = datetime.now(ZoneInfo("Asia/Seoul"))
        values = [self._snapshot_values(snapshot, collected_at) for snapshot in snapshots]
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO etf_daily_snapshots (
                    base_date, ticker, name, market, manager, listing_date, listing_status, close_price_krw,
                    previous_close_change_krw, fluctuation_rate, nav, open_price_krw,
                    high_price_krw, low_price_krw, trade_volume, trade_value_krw,
                    market_cap_krw, net_assets_krw, listed_shares, index_name,
                    index_close, index_previous_change, index_fluctuation_rate,
                    asset_types_json, classification_source, currency, source, collected_at
                ) VALUES (
                    :base_date, :ticker, :name, :market, :manager, :listing_date, :listing_status, :close_price_krw,
                    :previous_close_change_krw, :fluctuation_rate, :nav, :open_price_krw,
                    :high_price_krw, :low_price_krw, :trade_volume, :trade_value_krw,
                    :market_cap_krw, :net_assets_krw, :listed_shares, :index_name,
                    :index_close, :index_previous_change, :index_fluctuation_rate,
                    :asset_types_json, :classification_source, 'KRW', :source, :collected_at
                ) ON CONFLICT(base_date, ticker) DO UPDATE SET
                    name=excluded.name, market=excluded.market, manager=excluded.manager,
                    listing_date=excluded.listing_date, listing_status=excluded.listing_status,
                    close_price_krw=excluded.close_price_krw,
                    previous_close_change_krw=excluded.previous_close_change_krw,
                    fluctuation_rate=excluded.fluctuation_rate, nav=excluded.nav,
                    open_price_krw=excluded.open_price_krw, high_price_krw=excluded.high_price_krw,
                    low_price_krw=excluded.low_price_krw, trade_volume=excluded.trade_volume,
                    trade_value_krw=excluded.trade_value_krw, market_cap_krw=excluded.market_cap_krw,
                    net_assets_krw=excluded.net_assets_krw, listed_shares=excluded.listed_shares,
                    index_name=excluded.index_name, index_close=excluded.index_close,
                    index_previous_change=excluded.index_previous_change,
                    index_fluctuation_rate=excluded.index_fluctuation_rate,
                    asset_types_json=excluded.asset_types_json,
                    classification_source=excluded.classification_source,
                    source=excluded.source, collected_at=excluded.collected_at
                """,
                values,
            )
            connection.execute(
                """
                INSERT INTO etf_collection_runs (sync_date, as_of_date, record_count, source, completed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(sync_date) DO UPDATE SET
                    as_of_date=excluded.as_of_date, record_count=excluded.record_count,
                    source=excluded.source, completed_at=excluded.completed_at
                """,
                (
                    self._today_kst(),
                    as_of_date,
                    sum(snapshot.as_of_date == as_of_date for snapshot in snapshots),
                    KRX_SOURCE,
                    collected_at.isoformat(),
                ),
            )
        latest_snapshots = [snapshot for snapshot in snapshots if snapshot.as_of_date == as_of_date]
        return CachedEtfSnapshot(
            snapshots=latest_snapshots,
            as_of_date=as_of_date,
            collected_at=collected_at,
        )

    def existing_base_dates(self, start_date: str, end_date: str) -> set[str]:
        """Return stored KRX base dates in an inclusive YYYYMMDD range."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT base_date
                FROM etf_daily_snapshots
                WHERE base_date BETWEEN ? AND ?
                """,
                (start_date, end_date),
            ).fetchall()
        return {str(row["base_date"]) for row in rows}

    def has_history_through(self, target_date: str) -> bool:
        """Whether at least one ETF daily snapshot exists on or before ``target_date``."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT MIN(base_date) AS earliest_base_date FROM etf_daily_snapshots"
            ).fetchone()
        return row is not None and row["earliest_base_date"] is not None and row["earliest_base_date"] <= target_date

    def load_history_for_tickers(
        self, tickers: list[str], start_date: str, end_date: str
    ) -> dict[str, list[EtfSnapshot]]:
        if not tickers:
            return {}
        placeholders = ", ".join("?" for _ in tickers)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM etf_daily_snapshots
                WHERE ticker IN ({placeholders}) AND base_date BETWEEN ? AND ?
                ORDER BY ticker, base_date
                """,
                [*tickers, start_date, end_date],
            ).fetchall()
        history: dict[str, list[EtfSnapshot]] = {ticker: [] for ticker in tickers}
        for row in rows:
            history[row["ticker"]].append(self._row_to_snapshot(row))
        return history

    @staticmethod
    def _snapshot_values(snapshot: EtfSnapshot, collected_at: datetime) -> dict[str, object]:
        return {
            "base_date": snapshot.as_of_date, "ticker": snapshot.ticker, "name": snapshot.name,
            "market": snapshot.market, "manager": snapshot.manager,
            "listing_date": snapshot.listing_date, "listing_status": snapshot.listing_status,
            "close_price_krw": snapshot.close_price_krw,
            "previous_close_change_krw": snapshot.previous_close_change_krw,
            "fluctuation_rate": snapshot.fluctuation_rate, "nav": snapshot.nav,
            "open_price_krw": snapshot.open_price_krw, "high_price_krw": snapshot.high_price_krw,
            "low_price_krw": snapshot.low_price_krw, "trade_volume": snapshot.trade_volume,
            "trade_value_krw": snapshot.trade_value_krw, "market_cap_krw": snapshot.market_cap_krw,
            "net_assets_krw": snapshot.net_assets_krw, "listed_shares": snapshot.listed_shares,
            "index_name": snapshot.raw_classification, "index_close": snapshot.index_close,
            "index_previous_change": snapshot.index_previous_change,
            "index_fluctuation_rate": snapshot.index_fluctuation_rate,
            "asset_types_json": json.dumps(sorted(snapshot.asset_types)),
            "classification_source": snapshot.classification_source,
            "source": KRX_SOURCE, "collected_at": collected_at.isoformat(),
        }

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> EtfSnapshot:
        return EtfSnapshot(
            ticker=row["ticker"], name=row["name"], market=row["market"],
            close_price_krw=row["close_price_krw"], trade_volume=row["trade_volume"],
            trade_value_krw=row["trade_value_krw"], as_of_date=row["base_date"],
            asset_types=frozenset(json.loads(row["asset_types_json"])),
            classification_source=row["classification_source"], raw_classification=row["index_name"],
            previous_close_change_krw=row["previous_close_change_krw"],
            fluctuation_rate=row["fluctuation_rate"], nav=row["nav"],
            open_price_krw=row["open_price_krw"], high_price_krw=row["high_price_krw"],
            low_price_krw=row["low_price_krw"], market_cap_krw=row["market_cap_krw"],
            net_assets_krw=row["net_assets_krw"], listed_shares=row["listed_shares"],
            index_close=row["index_close"], index_previous_change=row["index_previous_change"],
            index_fluctuation_rate=row["index_fluctuation_rate"],
            manager=row["manager"], listing_date=row["listing_date"],
            listing_status=row["listing_status"],
        )
