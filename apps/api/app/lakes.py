from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import (optional_verify_supabase_jwt,
                      require_catalog_create_permission,
                      require_catalog_disable_permission,
                      require_catalog_update_permission)
from app.database import supabase
from app.permissions import CATALOG_ACTIONS, has_permission
from app.repositories import (_convert_wkt_to_polygon,
                              get_lake_stations_from_db, get_lakes_repository)
from app.responses import COMMON_ERRORS
from app.schemas import (LakeCreate, LakeDetail, LakeUpdate, PaginatedLakes,
                         StationOut)
from app.services import disable_lake, get_lake_by_id, log_audit_event

router = APIRouter(prefix="/api/v1/lakes", tags=["Catalog"])


def _convert_polygon_to_wkt(geom: dict) -> str | None:
    """Convierte un diccionario GeoJSON Polygon a una cadena WKT para PostGIS."""
    if not geom or geom.get("type") != "Polygon":
        return None
    rings = []
    for ring in geom.get("coordinates", []):
        points = ", ".join([f"{lon} {lat}" for lon, lat in ring])
        rings.append(f"({points})")
    return f"POLYGON({', '.join(rings)})"


@router.get("", response_model=PaginatedLakes, responses={**COMMON_ERRORS})
def get_lakes(
    text: str | None = Query(None, min_length=3, strip_whitespace=True, description="Filtro de búsqueda por nombre"),
    region: str | None = Query(None, description="Filtro exacto por región"),
    status_filter: str | None = Query(
        None, alias="status", description="Filtro exacto por estado"
    ),
    page: int = Query(1, ge=1, description="Número de página actual"),
    limit: int = Query(
        10, ge=1, le=100, description="Límite máximo de ítems por página"
    ),
    current_user: dict | None = Depends(optional_verify_supabase_jwt),  # noqa: B008
):
    """Recupera el catálogo de lagos con soporte para filtros combinados y paginación."""
    if status_filter == "inactive" and not has_permission(
        current_user, CATALOG_ACTIONS["DISABLE"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para consultar lagos inactivos.",
        )
    try:
        return get_lakes_repository(
            supabase,
            text=text,
            region=region,
            status_filter=status_filter,
            page=page,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al recuperar el catálogo: {exc}",
        ) from exc


@router.get("/{lake_id}", response_model=LakeDetail, responses={**COMMON_ERRORS})
def get_lake(lake_id: UUID):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    try:
        return get_lake_by_id(supabase=supabase, lake_id=lake_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("", response_model=LakeDetail, status_code=status.HTTP_201_CREATED, responses={**COMMON_ERRORS})
def create_lake(
    lake_create: LakeCreate,
    _payload: dict = Depends(require_catalog_create_permission),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    lake_data = lake_create.model_dump()
    geom = lake_data.get("geom")
    if geom:
        lake_data["geom"] = _convert_polygon_to_wkt(geom)

    try:
        response = supabase.table("lakes").insert(lake_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno al persistir el registro del lago (respuesta vacía).",
            )

        created_lake = response.data[0]

        actor_id = _payload.get("sub", "system")
        log_audit_event(supabase, actor_id, "CREATE", "lake", created_lake["id"], lake_data)

        if isinstance(created_lake.get("geom"), str):
            created_lake["geom"] = _convert_wkt_to_polygon(created_lake["geom"])
        return created_lake

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al crear el lago: {exc}",
        ) from exc


@router.patch("/{lake_id}", response_model=LakeDetail, responses={**COMMON_ERRORS})
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

    try:
        existing = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al verificar el lago: {exc}",
        ) from exc

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    update_data = lake_update.model_dump(exclude_unset=True)
    if "id" in update_data:
        del update_data["id"]

    if update_data.get("geom"):
        update_data["geom"] = _convert_polygon_to_wkt(update_data["geom"])

    if not update_data:
        return existing.data[0]

    try:
        response = (
            supabase.table("lakes").update(update_data).eq("id", str(lake_id)).execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar el lago (respuesta vacía).",
            )

        updated_lake = response.data[0]

        actor_id = _payload.get("sub", "system")
        log_audit_event(supabase, actor_id, "UPDATE", "lake", updated_lake["id"], update_data)

        return updated_lake

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al actualizar el lago: {exc}",
        ) from exc


@router.delete("/{lake_id}", response_model=LakeDetail, responses={**COMMON_ERRORS})
def delete_lake(
    lake_id: UUID,
    current_user: dict = Depends(require_catalog_disable_permission),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    try:
        disabled_lake = disable_lake(
            lake_id=lake_id, current_user=current_user, supabase=supabase
        )
        actor_id = current_user.get("sub", "system")
        log_audit_event(
            supabase,
            actor_id,
            "DEACTIVATE",
            "lake",
            disabled_lake["id"],
            {"status": "inactive"},
        )
        return disabled_lake
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al desactivar el lago: {exc}",
        ) from exc


@router.get("/{lake_id}/stations", response_model=list[StationOut], responses={**COMMON_ERRORS})
def get_lake_stations(
    lake_id: UUID,
    status_filter: str | None = Query(None, description="Filtrar por estado"),
):
    try:
        stations = get_lake_stations_from_db(lake_id, status_filter)
        if stations is None:
            raise HTTPException(404, detail="Lake not found")
        return stations
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    