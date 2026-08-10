import logging
from datetime import date, timedelta
from typing import Any

import httpx

from app.core.config import Settings, settings
from app.models.etf import EtfSnapshot

logger = logging.getLogger(__name__)
KRX_ETF_DAILY_URL = "https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd"


class KrxCollectorError(Exception):
    """Safe error raised when the KRX ETF source cannot provide usable data."""


class KrxConfigurationError(KrxCollectorError):
    pass


class KrxETFCollector:
    """Adapter for KRX ETF daily-trading Open API service."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def collect_latest(self) -> list[EtfSnapshot]:
        """Collect the most recent KRX business date that has ETF data."""
        requested_dates = [date.today() - timedelta(days=offset) for offset in range(8)]
        for requested_date in requested_dates:
            snapshots = self.collect_for_dates([requested_date])
            if snapshots:
                return snapshots
        raise KrxCollectorError("KRX response does not contain usable ETF records.")

    def collect_for_dates(self, requested_dates: list[date]) -> list[EtfSnapshot]:
        """Collect daily ETF snapshots for the supplied dates.

        KRX returns no usable records for weekends and market holidays. Those dates are
        intentionally skipped so that an otherwise valid history backfill can continue.
        """
        if not self.settings.krx_api_key:
            raise KrxConfigurationError("KRX API key is not configured.")
        headers = {"AUTH_KEY": self.settings.krx_api_key}
        snapshots: list[EtfSnapshot] = []

        with httpx.Client(timeout=self.settings.krx_request_timeout_seconds) as client:
            for requested_date in requested_dates:
                payload = self._request(
                    client,
                    KRX_ETF_DAILY_URL,
                    {"basDd": requested_date.strftime("%Y%m%d")},
                    headers,
                )
                if payload is None:
                    continue
                records = self._extract_records(payload)
                normalized = [snapshot for record in records if (snapshot := self._normalize(record))]
                if normalized:
                    logger.info(
                        "krx_etf_collection_succeeded base_date=%s records=%s normalized=%s",
                        requested_date.strftime("%Y%m%d"), len(records), len(normalized),
                    )
                    snapshots.extend(normalized)
        return snapshots

    def _request(
        self,
        client: httpx.Client,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> Any | None:
        try:
            response = client.post(url, json=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as error:
            logger.warning("krx_etf_collection_failed error_type=%s", type(error).__name__)
            raise KrxCollectorError("KRX ETF data collection failed.") from error
        try:
            return response.json()
        except ValueError:
            logger.info("krx_etf_no_data_for_requested_date")
            return None

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            raise KrxCollectorError("KRX response does not contain ETF records.")
        queue: list[Any] = [payload]
        while queue:
            current = queue.pop(0)
            if isinstance(current, list) and all(isinstance(item, dict) for item in current):
                return current
            if isinstance(current, dict):
                queue.extend(current.values())
        raise KrxCollectorError("KRX response does not contain ETF records.")

    @staticmethod
    def _value(record: dict[str, Any], *aliases: str) -> Any:
        normalized = {str(key).upper(): value for key, value in record.items()}
        for alias in aliases:
            value = normalized.get(alias.upper())
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(str(value).replace(",", "").replace("+", "").strip())
        except ValueError:
            return None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value in (None, "", "-"):
            return None
        try:
            return float(str(value).replace(",", "").replace("+", "").strip())
        except ValueError:
            return None

    def _normalize(self, record: dict[str, Any]) -> EtfSnapshot | None:
        ticker = self._value(record, "ISU_SRT_CD", "ISU_CD", "TICKER", "종목코드")
        name = self._value(record, "ISU_ABBRV", "ISU_NM", "NAME", "종목명")
        close_price = self._as_int(self._value(record, "TDD_CLSPRC", "CLSPRC", "CLOSE_PRICE", "종가"))
        as_of_date = self._value(record, "BAS_DD", "TRD_DD", "DATE", "기준일")
        if not ticker or not name or not close_price or close_price <= 0 or not as_of_date:
            return None
        classification = str(self._value(record, "ETF_TYPE", "FUND_TYPE", "ASSET_TYPE", "IDX_IND_NM", "IDX_NM", "기초지수명") or "")
        asset_types, source = self._classify(str(name), classification)
        return EtfSnapshot(
            ticker=str(ticker), name=str(name), market=self._value(record, "MKT_NM", "MARKET", "시장구분"),
            close_price_krw=close_price,
            trade_volume=self._as_int(self._value(record, "ACC_TRDVOL", "TRADE_VOLUME", "거래량")),
            trade_value_krw=self._as_int(self._value(record, "ACC_TRDVAL", "TRADE_VALUE", "거래대금")),
            as_of_date=str(as_of_date), asset_types=asset_types, classification_source=source,
            raw_classification=classification or None,
            previous_close_change_krw=self._as_int(self._value(record, "CMPPREVDD_PRC")),
            fluctuation_rate=self._as_float(self._value(record, "FLUC_RT")),
            nav=self._as_float(self._value(record, "NAV")),
            open_price_krw=self._as_int(self._value(record, "TDD_OPNPRC")),
            high_price_krw=self._as_int(self._value(record, "TDD_HGPRC")),
            low_price_krw=self._as_int(self._value(record, "TDD_LWPRC")),
            market_cap_krw=self._as_int(self._value(record, "MKTCAP")),
            net_assets_krw=self._as_int(self._value(record, "INVSTASST_NETASST_TOTAMT")),
            listed_shares=self._as_int(self._value(record, "LIST_SHRS")),
            index_close=self._as_float(self._value(record, "OBJ_STKPRC_IDX")),
            index_previous_change=self._as_float(self._value(record, "CMPPREVDD_IDX")),
            index_fluctuation_rate=self._as_float(self._value(record, "FLUC_RT_IDX")),
        )

    @staticmethod
    def _classify(name: str, classification: str) -> tuple[frozenset[str], str]:
        text = f"{name} {classification}".upper()
        source = "krx" if classification else "keyword_fallback"
        if any(keyword in text for keyword in ("레버리지", "인버스", "LEVERAGE", "INVERSE")):
            return frozenset({"restricted"}), source
        asset_types: set[str] = set()
        if any(keyword in text for keyword in ("채권", "BOND", "국채", "회사채")):
            asset_types.add("bond")
        if any(keyword in text for keyword in ("MMF", "머니마켓", "CASH", "단기자금")):
            asset_types.add("cash")
        if any(keyword in text for keyword in ("배당", "DIVIDEND")):
            asset_types.update({"equity", "dividend"})
        if not asset_types:
            asset_types.add("equity")
        return frozenset(asset_types), source
