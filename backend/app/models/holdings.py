from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EtfConstituent:
    """One ETF constituent from the manager's official PDF data."""

    constituent_code: str
    constituent_name: str
    weight_percent: float
    quantity: int | None = None
    evaluation_amount_krw: int | None = None
    current_price_krw: int | None = None
    price_change_krw: int | None = None


@dataclass(frozen=True)
class EtfConstituentSnapshot:
    """A dated, provider-attributed collection of ETF constituents."""

    ticker: str
    etf_name: str
    provider: str
    product_id: str
    as_of_date: str
    source_url: str
    collected_at: datetime
    source_record_count: int
    excluded_record_count: int
    constituents: list[EtfConstituent]
