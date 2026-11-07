import logging
import uuid
from datetime import date
from typing import Annotated
from uuid import UUID

from apps.api.app.core.auth import (
    optional_verify_supabase_jwt,
    require_catalog_create_permission,
    require_catalog_disable_permission,
    require_catalog_update_permission,
)
from apps.api.app.core.database import supabase
from apps.api.app.core.permissions import CATALOG_ACTIONS, has_permission
from apps.api.app.core.responses import COMMON_ERRORS
from apps.api.app.domains.catalog.domain_catalog import (
    convert_polygon_to_wkt,
    convert_wkt_to_polygon,
    validate_station_inside_lake,
)
from apps.api.app.domains.catalog.model_catalog import (
    get_lake_geom_by_id,
    get_lake_stations_from_db,
    get_lakes_repository,
    get_station_by_id_from_db,
    insert_lake_in_db,
    insert_station_in_db,
    query_lake_scenes_from_db,
    station_code_exists_in_lake,
    update_lake_in_db,
    update_station_in_db,
)
from apps.api.app.domains.catalog.schemas_catalog import (
    LakeCreate,
    LakeDetail,
    LakeUpdate,
    PaginatedLakes,
    PaginatedScenes,
    StationCreate,
    StationOut,
    StationUpdate,
)
from apps.api.app.domains.catalog.service_catalog import disable_lake, get_lake_by_id
from apps.api.app.domains.identity.service_identity import log_audit_event
from fastapi import APIRouter, Depends, HTTPException, Query, status

router = APIRouter()
lakes_router = APIRouter(prefix="/api/v1/lakes", tags=["Catalog"])
stations_router = APIRouter(prefix="/api/v1/stations", tags=["Catalog"])
logger = logging.getLogger(__name__)


# --- Endpoints de Lakes ---


@lakes_router.get("", response_model=PaginatedLakes, responses={**COMMON_ERRORS})
def get_lakes(
    text: str | None = Query(
        None,
        min_length=3,
        strip_whitespace=True,
        description="Filtro de búsqueda por nombre",
    ),
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


@lakes_router.get("/{lake_id}/scenes", response_model=PaginatedScenes)
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La fecha inicial debe ser anterior o igual a la fecha final.",
        )

    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    try:
        lake_row = get_lake_geom_by_id(supabase, lake_id)
    except Exception as exc:
        logger.exception("No se pudo comprobar el lago antes de listar escenas.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo consultar el lago.",
        ) from exc

    if not lake_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    offset = (page - 1) * page_size

    try:
        items, total = query_lake_scenes_from_db(
            supabase, lake_id, start_date, end_date, offset, page_size
        )
    except Exception as exc:
        logger.exception("No se pudieron consultar las escenas registradas.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron consultar las escenas registradas.",
        ) from exc

    return PaginatedScenes(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@lakes_router.get("/{lake_id}", response_model=LakeDetail, responses={**COMMON_ERRORS})
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


@lakes_router.post(
    "",
    response_model=LakeDetail,
    status_code=status.HTTP_201_CREATED,
    responses={**COMMON_ERRORS},
)
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
        lake_data["geom"] = convert_polygon_to_wkt(geom)

    try:
        created_lake = insert_lake_in_db(supabase, lake_data)
        if not created_lake:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno al persistir el registro del lago (respuesta vacía).",
            )

        actor_id = _payload.get("sub", "system")
        log_audit_event(
            supabase, actor_id, "CREATE", "lake", created_lake["id"], lake_data
        )

        if isinstance(created_lake.get("geom"), str):
            created_lake["geom"] = convert_wkt_to_polygon(created_lake["geom"])
        return created_lake

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al crear el lago: {exc}",
        ) from exc


@lakes_router.patch("/{lake_id}", response_model=LakeDetail, responses={**COMMON_ERRORS})
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
        existing_lake = get_lake_by_id(supabase, lake_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al verificar el lago: {exc}",
        ) from exc

    update_data = lake_update.model_dump(exclude_unset=True)
    if "id" in update_data:
        del update_data["id"]

    if update_data.get("geom"):
        update_data["geom"] = convert_polygon_to_wkt(update_data["geom"])

    if not update_data:
        return existing_lake

    try:
        updated_lake = update_lake_in_db(supabase, lake_id, update_data)
        if not updated_lake:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar el lago (respuesta vacía).",
            )

        actor_id = _payload.get("sub", "system")
        log_audit_event(
            supabase, actor_id, "UPDATE", "lake", updated_lake["id"], update_data
        )

        if isinstance(updated_lake.get("geom"), str):
            updated_lake["geom"] = convert_wkt_to_polygon(updated_lake["geom"])
        return updated_lake

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al actualizar el lago: {exc}",
        ) from exc


@lakes_router.delete("/{lake_id}", response_model=LakeDetail, responses={**COMMON_ERRORS})
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


# --- Endpoints de Stations ---


@lakes_router.get(
    "/{lake_id}/stations", response_model=list[StationOut], responses={**COMMON_ERRORS}
)
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


@lakes_router.post(
    "/{lake_id}/stations",
    status_code=201,
    dependencies=[Depends(require_catalog_create_permission)],
)
def create_station(lake_id: uuid.UUID, payload: StationCreate):
    """Crea una nueva estación asociada a un lago utilizando el cliente oficial de Supabase."""
    lake_row = get_lake_geom_by_id(supabase, lake_id)
    if not lake_row:
        raise HTTPException(
            status_code=404,
            detail="El lago asociado no existe.",
        )

    lake_geom = lake_row.get("geom")
    if lake_geom:
        try:
            validate_station_inside_lake(
                lake_geojson=lake_geom, lat=payload.latitude, lon=payload.longitude
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    if station_code_exists_in_lake(supabase, lake_id, payload.code):
        raise HTTPException(
            status_code=409,
            detail="El código de la estación ya existe para este lago.",
        )

    wkt_geom = f"POINT({payload.longitude} {payload.latitude})"
    station_data = {
        "lake_id": str(lake_id),
        "code": payload.code,
        "name": payload.name,
        "description": payload.description,
        "status": payload.status or "active",
        "point": wkt_geom,
    }

    created_station = insert_station_in_db(supabase, station_data)
    if not created_station:
        raise HTTPException(
            status_code=500, detail="Error al crear la estación en la base de datos."
        )

    return {
        "id": created_station.get("id"),
        "message": "Estación creada exitosamente.",
    }


@stations_router.patch("/{station_id}", responses={**COMMON_ERRORS})
def update_station(
    station_id: UUID,
    station_update: StationUpdate,
    _payload: dict = Depends(require_catalog_update_permission),  # noqa: B008
):
    """Actualiza parcialmente una estación. Protege el código y la relación con el lago."""
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )

    existing_station = get_station_by_id_from_db(supabase, station_id)
    if not existing_station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La estación con id {station_id} no existe.",
        )

    update_data = station_update.model_dump(exclude_unset=True)

    if "coordinates" in update_data:
        coords = update_data.pop("coordinates")
        if coords:
            lat = coords["latitude"]
            lon = coords["longitude"]
            update_data["point"] = f"POINT({lon} {lat})"

    if not update_data:
        return existing_station

    try:
        station = update_station_in_db(supabase, station_id, update_data)
        if not station:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se devolvieron datos tras la actualización.",
            )

        actor_id = _payload.get("sub", "system")
        log_audit_event(
            supabase, actor_id, "UPDATE", "station", station["id"], update_data
        )
        return station
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos: {exc}",
        ) from exc


router.include_router(lakes_router)
router.include_router(stations_router)
