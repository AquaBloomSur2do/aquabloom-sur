from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_catalog_update_permission
from app.database import supabase
from app.schemas import LakeDetail, LakeUpdate

router = APIRouter(prefix="/api/v1/lakes", tags=["Catalog"])

@router.patch("/{lake_id}", response_model=LakeDetail)
def update_lake(lake_id: UUID, lake_update: LakeUpdate, _payload: dict = Depends(require_catalog_update_permission)):  # noqa: B008
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible"
        )

    # 1. Verificar si el lago existe
    existing = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe."
        )

    # 2. Filtrar únicamente los campos enviados (excluyendo explícitamente el id)
    update_data = lake_update.model_dump(exclude_unset=True)
    if "id" in update_data:
        del update_data["id"]

    if not update_data:
        return existing.data[0]

    # 3. Ejecutar actualización en la base de datos
    response = supabase.table("lakes").update(update_data).eq("id", str(lake_id)).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar el lago."
        )

    return response.data[0]

