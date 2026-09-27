from uuid import UUID

from app.auth import require_catalog_update_permission
from app.database import supabase
from app.schemas import StationUpdate
from app.services import validate_station_inside_lake
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1/stations", tags=["Catalog"])


@router.patch("/{station_id}")
def update_station(
    station_id: UUID,
    station_update: StationUpdate,
    _payload: dict = Depends(require_catalog_update_permission),  # noqa: B008
):
    """
    Actualiza parcialmente una estación. Protege el código y la relación con el lago.
    """
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )

    # 1. Verificar existencia
    existing = (
        supabase.table("stations").select("*").eq("id", str(station_id)).execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La estación con id {station_id} no existe.",
        )

    # 2. Extracción segura (exclude_unset=True ignora lo que el cliente no envió)
    update_data = station_update.model_dump(exclude_unset=True)

    # Transformación a formato WKT (Well-Known Text) para PostGIS y validacion geoespacial
    if "coordinates" in update_data:
        coords = update_data.pop("coordinates")
        if coords:
            lat = coords["latitude"]
            lon = coords["longitude"]
            
            # Validación geoespacial 
            lake_id = existing.data[0].get("lake_id")
            if lake_id:
                lake_res = supabase.table("lakes").select("geom").eq("id", lake_id).execute()
                if lake_res.data and lake_res.data[0].get("geom"):
                    try:
                        validate_station_inside_lake(
                            lake_geojson=lake_res.data[0]["geom"], 
                            lat=lat, 
                            lon=lon
                        )
                    except ValueError as e:
                        raise HTTPException(status_code=422, detail=str(e))

            # PostGIS espera longitud primero, luego latitud: 'POINT(lon lat)'
            update_data["geom"] = f"POINT({lon} {lat})"

    # 3. Optimización: Interceptar transacciones vacías
    if not update_data:
        return existing.data[0]

    # 4. Mutación atómica
    try:
        response = (
            supabase.table("stations")
            .update(update_data)
            .eq("id", str(station_id))
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se devolvieron datos tras la actualización.",
            )
        return response.data[0]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos: {exc}",
        ) from exc
