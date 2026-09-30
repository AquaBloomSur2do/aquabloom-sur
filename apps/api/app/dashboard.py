from app.auth import verify_supabase_jwt
from app.database import supabase
from app.schemas import DashboardSummaryResponse
from app.services import get_dashboard_summary
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )
    return get_dashboard_summary(supabase, payload)