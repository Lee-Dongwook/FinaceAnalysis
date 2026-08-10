"""ETF constituent endpoint."""

from fastapi import APIRouter, HTTPException

from app.api.schemas.analysis import EtfHoldingsResponse
from app.core.config import settings
from app.core.etf_cache import SqliteEtfCache
from app.services.holdings_service import EtfHoldingsNotFoundError, get_etf_holdings


router = APIRouter(tags=["holdings"])


@router.get("/api/etfs/{ticker}/holdings", response_model=EtfHoldingsResponse)
def get_holdings(ticker: str) -> EtfHoldingsResponse:
    """Return constituents from the supported manager's official PDF data."""
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=400, detail="ETF ticker is invalid.")
    try:
        return get_etf_holdings(ticker.upper(), SqliteEtfCache(settings.etf_database_path))
    except EtfHoldingsNotFoundError as error:
        raise HTTPException(status_code=404, detail="Current ETF data does not contain the requested ticker.") from error
