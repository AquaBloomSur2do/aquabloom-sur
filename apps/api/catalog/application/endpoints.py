import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_catalog_create_permission
from app.database import supabase

from .schemas import StationCreate

router = APIRouter()


@router.post(
    "/api/v1/lakes/{lake_id}/stations",
    status_code=201,
    dependencies=[Depends(require_catalog_create_permission)],
)
def create_station(lake_id: uuid.UUID, payload: StationCreate):
    """Crea una nueva estación asociada a un lago utilizando el cliente oficial de Supabase.

    Implementa validación de código único y geometría WKT (SRID 4326).
    """
    # 1. Validación (409 Conflict): Verificar si el código ya existe para el lake_id
    existing_check = (
        supabase.table("station")
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

    # 2. Inserción con PostGIS usando formato WKT
    wkt_geom = f"POINT({payload.longitude} {payload.latitude})"

    station_data = {
        "lake_id": str(lake_id),
        "code": payload.code,
        "name": payload.name,
        "source": payload.source,
        "activity": payload.activity,
        "geom": wkt_geom,
    }

    response = supabase.table("station").insert(station_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=500, detail="Error al crear la estación en la base de datos."
        )

    created_station = response.data[0]

    return {
        "id": created_station.get("id"),
        "message": "Estación creada exitosamente.",
    }
