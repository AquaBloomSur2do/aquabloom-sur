from datetime import date
from typing import Annotated
from uuid import UUID

from apps.satellite.app.core.auth import verify_supabase_jwt
from apps.satellite.app.core.database import supabase
from apps.satellite.app.domains.scenes.schemas_scenes import PaginatedScenes
from apps.satellite.app.domains.scenes.service_scenes import list_scenes_service
from fastapi import APIRouter, Depends, HTTPException, Query, status

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
    client = _require_database()
    return list_scenes_service(
        client,
        lake_id=lake_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    
