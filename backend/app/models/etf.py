from dataclasses import dataclass


@dataclass(frozen=True)
class EtfSnapshot:
    ticker: str
    name: str
    market: str | None
    close_price_krw: int
    trade_volume: int | None
    trade_value_krw: int | None
    as_of_date: str
    asset_types: frozenset[str]
    classification_source: str
    raw_classification: str | None = None
    previous_close_change_krw: int | None = None
    fluctuation_rate: float | None = None
    nav: float | None = None
    open_price_krw: int | None = None
    high_price_krw: int | None = None
    low_price_krw: int | None = None
    market_cap_krw: int | None = None
    net_assets_krw: int | None = None
    listed_shares: int | None = None
    index_close: float | None = None
    index_previous_change: float | None = None
    index_fluctuation_rate: float | None = None
    manager: str | None = None
    listing_date: str | None = None
    listing_status: str | None = None
