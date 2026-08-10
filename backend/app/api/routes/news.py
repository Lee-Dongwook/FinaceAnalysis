"""Manual, single-ETF news analysis endpoint."""

from fastapi import APIRouter, HTTPException

from app.api.schemas.analysis import NewsCandidateAnalysisRequest, NewsCandidateAnalysisResponse
from app.collectors.naver_news import NaverNewsCollectorError
from app.core.config import settings
from app.core.etf_cache import SqliteEtfCache
from app.services.candidate_news_service import CandidateNewsNotFoundError, analyze_one_candidate_news


router = APIRouter(tags=["news"])


@router.post("/api/news-analyses", response_model=NewsCandidateAnalysisResponse)
def create_candidate_news_analysis(request: NewsCandidateAnalysisRequest) -> NewsCandidateAnalysisResponse:
    """Inspect one ETF's validated, recent news and its sentiment result."""
    try:
        return analyze_one_candidate_news(request, SqliteEtfCache(settings.etf_database_path))
    except CandidateNewsNotFoundError as error:
        raise HTTPException(status_code=404, detail="Current ETF data does not contain the requested ticker.") from error
    except NaverNewsCollectorError as error:
        raise HTTPException(status_code=502, detail="News search is unavailable. Check NAVER API settings.") from error
