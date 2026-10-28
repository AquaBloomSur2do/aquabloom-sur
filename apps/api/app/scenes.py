import logging
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.database import supabase
from app.schemas import PaginatedScenes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scenes"])


@router.get("/api/v1/lakes/{lake_id}/scenes", response_model=PaginatedScenes)
def list_lake_scenes(
    lake_id: UUID,
    start_date: Annotated[
        date, Query(description="Fecha inicial inclusiva (YYYY-MM-DD)")
    ],
    end_date: Annotated[date, Query(description="Fecha final inclusiva (YYYY-MM-DD)")],
    page: Annotated[int, Query(ge=1, description="Número de página")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Máximo 100 escenas")
    ] = 20,
) -> PaginatedScenes:
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha inicial debe ser anterior o igual a la fecha final.",
        )

    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    try:
        lake_response = (
            supabase.table("lakes")
            .select("id")
            .eq("id", str(lake_id))
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.exception("No se pudo comprobar el lago antes de listar escenas.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo consultar el lago.",
        ) from exc

    if not lake_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    offset = (page - 1) * page_size

    try:
        response = (
            supabase.table("scenes")
            .select(
                "id, lake_id, scene_identifier, acquisition_date, created_at",
                count="exact",
            )
            .eq("lake_id", str(lake_id))
            .gte("acquisition_date", start_date.isoformat())
            .lte("acquisition_date", end_date.isoformat())
            .order("acquisition_date", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
    except Exception as exc:
        logger.exception("No se pudieron consultar las escenas registradas.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron consultar las escenas registradas.",
        ) from exc

    return PaginatedScenes(
        items=response.data or [],
        page=page,
        page_size=page_size,
        total=response.count or 0,
    )
