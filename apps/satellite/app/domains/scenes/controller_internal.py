from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from apps.satellite.app.core.auth import require_internal_service
from apps.satellite.app.core.database import supabase
from apps.satellite.app.domains.scenes.model_scenes import get_scene_metadata_by_id

router = APIRouter(prefix="/internal/v1/scenes", tags=["Internal"])


@router.get("/{scene_id}")
def get_scene_metadata(
    scene_id: UUID,
    _token: None = Depends(require_internal_service),
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    scene = get_scene_metadata_by_id(supabase, scene_id)
    if scene is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escena no encontrada.",
        )
    return scene
