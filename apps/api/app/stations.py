from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_catalog_update_permission
from app.database import supabase
from app.schemas import StationUpdate

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

    # Si enviaron coordinates, lo extraemos a un formato compatible con tu base de datos (dict)
    if update_data.get("coordinates"):
        # Mantenemos la estructura JSON plano para la base de datos
        update_data["coordinates"] = update_data["coordinates"]

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
