from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.responses import COMMON_ERRORS

router = APIRouter(prefix="/api/v1/scenes", tags=["Scenes"])


class SceneDetail(BaseModel):
    id: str
    procedencia: str = Field(..., description="Fuente y origen de la escena satelital")
    checksum: str = Field(..., description="Hash de verificación de integridad")
    calidad: str = Field(..., description="Métrica de calidad o cobertura de la escena")


MOCK_SCENES_DB = {
    "S2A_MSIL2A_TEST_001": {
        "procedencia": "Copernicus Sentinel-2 L2A",
        "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "calidad": "98% píxeles válidos",
    }
}


@router.get("/{scene_id}", response_model=SceneDetail, responses={**COMMON_ERRORS})
def get_scene_detail(scene_id: str):
    """
    Expone los detalles técnicos y de procedencia de una escena satelital.
    """
    scene = MOCK_SCENES_DB.get(scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El identificador de escena '{scene_id}' no existe.",
        )

    return SceneDetail(id=scene_id, **scene)
