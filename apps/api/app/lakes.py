from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import require_catalog_update_permission
from app.database import supabase
from app.schemas import LakeDetail, LakeUpdate, PaginatedLakes

router = APIRouter(prefix="/api/v1/lakes", tags=["Catalog"])


@router.get("", response_model=PaginatedLakes)
def get_lakes(
    text: str | None = Query(None, description="Filtro de búsqueda por nombre"),
    region: str | None = Query(None, description="Filtro exacto por región"),
    status_filter: str | None = Query(
        None, alias="status", description="Filtro exacto por estado"
    ),
    page: int = Query(1, ge=1, description="Número de página actual"),
    limit: int = Query(
        10, ge=1, le=100, description="Límite máximo de ítems por página"
    ),
):
    """
    Recupera el catálogo de lagos con soporte para filtros combinados y paginación estructurada.
    """
    try:
        # Iniciamos la consulta solicitando los datos y el conteo total exacto
        query = supabase.table("lakes").select("*", count="exact")

        # Aplicación dinámica de filtros
        if text:
            query = query.ilike("name", f"%{text}%")
        if region:
            query = query.eq("region", region)
        if status_filter:
            query = query.eq("status", status_filter)

        # Cálculo de rangos para la paginación de Supabase (Zero-indexed)
        start = (page - 1) * limit
        end = start + limit - 1
        query = query.range(start, end)

        # Ejecución atómica de la consulta
        response = query.execute()
        total_count = response.count if response.count is not None else 0

        # Mapeo estricto al contrato Pydantic
        return {
            "items": response.data,
            "page": page,
            "page_size": limit,
            "total": total_count,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al recuperar el catálogo: {exc}",
        ) from exc


@router.patch("/{lake_id}", response_model=LakeDetail)
def update_lake(
    lake_id: UUID,
    lake_update: LakeUpdate,
    _payload: dict = Depends(require_catalog_update_permission),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    # 1. Verificar si el lago existe
    existing = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    # 2. Filtrar únicamente los campos enviados (excluyendo explícitamente el id)
    update_data = lake_update.model_dump(exclude_unset=True)
    if "id" in update_data:
        del update_data["id"]

    if not update_data:
        return existing.data[0]

    # 3. Ejecutar actualización en la base de datos
    response = (
        supabase.table("lakes").update(update_data).eq("id", str(lake_id)).execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar el lago.",
        )

    return response.data[0]
