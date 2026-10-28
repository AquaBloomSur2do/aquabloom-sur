from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import verify_supabase_jwt
from app.database import supabase
from app.schemas import DashboardSummaryResponse, ProfileOption
from app.services import get_dashboard_summary

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )
    return get_dashboard_summary(supabase, payload)


@router.get("/profiles", response_model=list[ProfileOption])
def dashboard_profiles(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )
    try:
        response = (
            supabase.table("profiles")
            .select("id, email, name")
            .order("name")
            .execute()
        )
        return response.data or []
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los perfiles: {exc!s}",
        ) from exc
    