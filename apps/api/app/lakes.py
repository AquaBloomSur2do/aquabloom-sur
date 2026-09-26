from uuid import UUID

from app.auth import (
    require_catalog_create_permission,
    require_catalog_disable_permission,
    require_catalog_update_permission,
)
from app.database import supabase
from app.schemas import LakeCreate, LakeDetail, LakeUpdate, PaginatedLakes
from fastapi import APIRouter, Depends, HTTPException, Query, status

router = APIRouter(prefix="/api/v1/lakes", tags=["Catalog"])

@router.get("", response_model=PaginatedLakes)
def get_lakes(
    text: str | None = Query(None, description="Filtro de búsqueda por nombre"),
    region: str | None = Query(None, description="Filtro exacto por región"),
    status_filter: str | None = Query(None, alias="status", description="Filtro exacto por estado"),
    page: int = Query(1, ge=1, description="Número de página actual"),
    limit: int = Query(10, ge=1, le=100, description="Límite máximo de ítems por página"),
):
    try:
        query = supabase.table("lakes").select("*", count="exact")

        if status_filter:
            query = query.eq("status", status_filter)
        else:
            query = query.neq("status", "inactive")

        if text:
            query = query.ilike("name", f"%{text}%")
        if region:
            query = query.eq("region", region)

        start = (page - 1) * limit
        end = start + limit - 1
        query = query.range(start, end)

        response = query.execute()
        total_count = response.count if response.count is not None else 0

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

@router.get("/{lake_id}", response_model=LakeDetail)
def get_lake(lake_id: UUID):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    existing = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    return existing.data[0]

@router.post("", response_model=LakeDetail, status_code=status.HTTP_201_CREATED)
def create_lake(
    lake_create: LakeCreate,
    _payload: dict = Depends(require_catalog_create_permission),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    lake_data = lake_create.model_dump()

    geom_type = str(lake_data["geometry"].get("type", "")).upper()
    coords = lake_data["geometry"].get("coordinates", [])

    def format_coords(c: list) -> str:
        if not c: return ""
        if isinstance(c[0], (int, float)):
            return f"{c[0]} {c[1]}"
        return "(" + ", ".join(format_coords(sub) for sub in c) + ")"

    try:
        if geom_type == "POINT":
            wkt_geometry = f"POINT({format_coords(coords)})"
        else:
            wkt_geometry = f"{geom_type}{format_coords(coords)}"
            
        lake_data["geometry"] = wkt_geometry
    except (TypeError, ValueError, IndexError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estructura de coordenadas GeoJSON inválida: {e}"
        )

    try:
        response = supabase.table("lakes").insert(lake_data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="La base de datos no retornó los datos del lago creado."
            )
            
        return response.data[0]
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del motor de base de datos al guardar el lago: {exc}"
        )

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

    existing = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    update_data = lake_update.model_dump(exclude_unset=True)
    if "id" in update_data:
        del update_data["id"]

    if not update_data:
        return existing.data[0]

    response = (
        supabase.table("lakes").update(update_data).eq("id", str(lake_id)).execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar el lago.",
        )

    return response.data[0]

@router.delete("/{lake_id}", response_model=LakeDetail)
def delete_lake(
    lake_id: UUID,
    _payload: dict = Depends(require_catalog_disable_permission),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    existing = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    update_data = {"status": "inactive"}
    response = (
        supabase.table("lakes").update(update_data).eq("id", str(lake_id)).execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al desactivar el lago.",
        )

    return response.data[0]
