import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings, settings
from app.models.etf import EtfSnapshot
from app.models.holdings import EtfConstituent, EtfConstituentSnapshot


logger = logging.getLogger(__name__)
KODEX_PROVIDER = "Samsung Asset Management KODEX official constituent PDF"


class KodexConstituentCollectorError(Exception):
    """Raised when the public KODEX constituent source cannot be used safely."""


class SamsungKodexConstituentCollector:
    """Adapter for the public KODEX product page's constituent-PDF data endpoint.

    The endpoint powers the "구성종목(PDF)" view on each official KODEX ETF page.
    It is intentionally limited to KODEX products; other managers require their own
    officially supported adapters and are reported as unsupported by the service.
    """

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.base_url = app_settings.samsung_fund_base_url.rstrip("/") + "/"

    def collect(self, etf: EtfSnapshot) -> EtfConstituentSnapshot:
        product = self._find_product(etf.ticker)
        product_id = self._required_text(product, "fId")
        product_name = str(product.get("fNm") or etf.name).strip()
        requested_date = self._format_date(etf.as_of_date)
        payload = self._get_json(
            f"api/v1/kodex/product-pdf/{product_id}.do",
            {"gijunYMD": requested_date},
        )
        pdf_data = payload.get("pdf") if isinstance(payload, dict) else None
        if not isinstance(pdf_data, dict):
            raise KodexConstituentCollectorError("KODEX constituent PDF response is invalid.")

        rows = pdf_data.get("list")
        if not isinstance(rows, list):
            raise KodexConstituentCollectorError("KODEX constituent PDF does not contain a list.")

        constituents: list[EtfConstituent] = []
        excluded = 0
        for row in rows:
            constituent = self._normalize_constituent(row)
            if constituent is None:
                excluded += 1
                continue
            constituents.append(constituent)
        if not constituents:
            raise KodexConstituentCollectorError("KODEX constituent PDF has no valid weighted holdings.")

        as_of_date = self._normalize_date(pdf_data.get("gijunYMD"), etf.as_of_date)
        source_url = urljoin(
            self.base_url,
            f"etf/product/view.do?id={product_id}",
        )
        logger.info(
            "kodex_constituent_collection_succeeded ticker=%s product_id=%s as_of_date=%s stored_records=%s excluded_records=%s",
            etf.ticker,
            product_id,
            as_of_date,
            len(constituents),
            excluded,
        )
        return EtfConstituentSnapshot(
            ticker=etf.ticker,
            etf_name=product_name,
            provider=KODEX_PROVIDER,
            product_id=product_id,
            as_of_date=as_of_date,
            source_url=source_url,
            collected_at=datetime.now(ZoneInfo("Asia/Seoul")),
            source_record_count=len(rows),
            excluded_record_count=excluded,
            constituents=constituents,
        )

    def _find_product(self, ticker: str) -> dict[str, Any]:
        payload = self._get_json(
            "api/v1/kodex/product.do",
            {
                "srchTerm": "w",
                "ordrSort": "DESC",
                "ordrColm": "NAV",
                "pageNo": "1",
                "pageRows": "20",
                "srchVal": ticker,
            },
        )
        if not isinstance(payload, list):
            raise KodexConstituentCollectorError("KODEX product search response is invalid.")
        product = next(
            (
                item for item in payload
                if isinstance(item, dict) and str(item.get("stkTicker", "")).strip() == ticker
            ),
            None,
        )
        if product is None:
            raise KodexConstituentCollectorError("KODEX product was not found for the ETF ticker.")
        return product

    def _get_json(self, path: str, params: dict[str, str]) -> Any:
        url = urljoin(self.base_url, path)
        try:
            with httpx.Client(timeout=self.settings.samsung_fund_request_timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("kodex_constituent_collection_failed error_type=%s", type(error).__name__)
            raise KodexConstituentCollectorError("KODEX official constituent source is unavailable.") from error

    @staticmethod
    def _required_text(data: dict[str, Any], key: str) -> str:
        value = str(data.get(key) or "").strip()
        if not value:
            raise KodexConstituentCollectorError("KODEX product information is incomplete.")
        return value

    @staticmethod
    def _format_date(value: str) -> str:
        if len(value) == 8 and value.isdigit():
            return f"{value[:4]}.{value[4:6]}.{value[6:]}"
        return value

    @staticmethod
    def _normalize_date(value: Any, fallback: str) -> str:
        normalized = str(value or "").strip().replace(".", "").replace("-", "")
        return normalized if len(normalized) == 8 and normalized.isdigit() else fallback

    @classmethod
    def _normalize_constituent(cls, row: Any) -> EtfConstituent | None:
        if not isinstance(row, dict):
            return None
        code = str(row.get("itmNo") or "").strip()
        name = str(row.get("secNm") or "").strip()
        weight = cls._to_float(row.get("ratio"))
        if not code or not name or weight is None or not 0 < weight <= 100:
            return None
        return EtfConstituent(
            constituent_code=code,
            constituent_name=name,
            weight_percent=weight,
            quantity=cls._to_int(row.get("applyQ")),
            evaluation_amount_krw=cls._to_int(row.get("evalA")),
            current_price_krw=cls._to_int(row.get("curp")),
            price_change_krw=cls._to_int(row.get("risep")),
        )

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(str(value).replace(",", "")) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(str(value).replace(",", "")) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None
