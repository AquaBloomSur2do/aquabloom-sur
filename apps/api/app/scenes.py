from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import verify_supabase_jwt
from app.database import supabase
from app.schemas import PaginatedScenes

router = APIRouter(prefix="/api/v1/scenes", tags=["Scenes"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )
    return supabase


@router.get("", response_model=PaginatedScenes)
def list_scenes(
    lake_id: Annotated[UUID, Query(description="ID del lago")],
    start_date: Annotated[date, Query(description="Fecha inicial")],
    end_date: Annotated[date, Query(description="Fecha final")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio no puede ser posterior a la fecha de fin.",
        )

    client = _require_database()
    lakes = (
        client.table("lakes")
        .select("id")
        .eq("id", str(lake_id))
        .execute()
    )
    if not lakes.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lago no encontrado.",
        )

    offset = (page - 1) * page_size
    response = (
        client.table("scenes")
        .select("id, lake_id, scene_identifier, acquisition_date, created_at", count="exact")
        .eq("lake_id", str(lake_id))
        .gte("acquisition_date", start_date.isoformat())
        .lte("acquisition_date", end_date.isoformat())
        .order("acquisition_date", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )

    return {
        "items": response.data or [],
        "page": page,
        "page_size": page_size,
        "total": response.count or 0,
    }
