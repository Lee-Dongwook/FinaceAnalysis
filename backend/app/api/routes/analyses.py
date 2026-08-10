"""Analysis request endpoint."""

from fastapi import APIRouter

from app.api.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis_service import run_analysis


router = APIRouter(tags=["analysis"])


@router.post("/api/analyses", response_model=AnalysisResponse)
def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Run the ETF analysis pipeline for validated investment conditions."""
    return run_analysis(request)
