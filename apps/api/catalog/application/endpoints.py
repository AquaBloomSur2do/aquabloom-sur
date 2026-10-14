import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_catalog_create_permission
from app.database import supabase
from app.services import validate_station_inside_lake

from .schemas import StationCreate

router = APIRouter()


@router.post(
    "/api/v1/lakes/{lake_id}/stations",
    status_code=201,
    dependencies=[Depends(require_catalog_create_permission)],
)
def create_station(lake_id: uuid.UUID, payload: StationCreate):
    """Crea una nueva estación asociada a un lago utilizando el cliente oficial de Supabase.

    Implementa validación de código único, límites geográficos y geometría WKT (SRID 4326).
    """
    lake_check = (
        supabase.table("lakes").select("id, geom").eq("id", str(lake_id)).execute()
    )

    if not lake_check.data:
        raise HTTPException(
            status_code=404,
            detail="El lago asociado no existe.",
        )

    lake_geom = lake_check.data[0].get("geom")
    if lake_geom:
        try:
            validate_station_inside_lake(
                lake_geojson=lake_geom, lat=payload.latitude, lon=payload.longitude
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing_check = (
        supabase.table("stations")
        .select("id")
        .eq("lake_id", str(lake_id))
        .eq("code", payload.code)
        .execute()
    )

    if existing_check.data and len(existing_check.data) > 0:
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

    response = supabase.table("stations").insert(station_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=500, detail="Error al crear la estación en la base de datos."
        )

    created_station = response.data[0]

    return {
        "id": created_station.get("id"),
        "message": "Estación creada exitosamente.",
    }
