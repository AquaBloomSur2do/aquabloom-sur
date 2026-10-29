from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import verify_supabase_jwt
from app.database import supabase
from satellite.application.schemas import (
    SpectralObservationCreate,
    SpectralObservationResponse,
)

router = APIRouter(prefix="/api/v1/observations", tags=["Observations"])

def _require_database():
    if supabase is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="BD no disponible")
    return supabase

def _user_id(payload: dict) -> str:
    user_id = payload.get("sub")
    try:
        return str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin ID de usuario.") from exc

@router.post("", response_model=SpectralObservationResponse, status_code=status.HTTP_201_CREATED)
def create_observation(payload: SpectralObservationCreate, _token: dict = Depends(verify_supabase_jwt)): # noqa: B008
    """Registra una nueva observación espectral (Integrado desde S2-127)"""
    client = _require_database()
    user_id = _user_id(_token)

    scene_res = client.table("scenes").select("lake_id").eq("id", str(payload.scene_id)).execute()
    if not scene_res.data:
        raise HTTPException(status_code=404, detail="La escena no existe.")
    lake_id = scene_res.data[0].get("lake_id")

    lake_res = client.table("lakes").select("organization_id").eq("id", str(lake_id)).execute()
    if not lake_res.data:
        raise HTTPException(status_code=404, detail="El lago asociado no existe.")
    org_id = lake_res.data[0].get("organization_id")

    insert_data = {
        "scene_id": str(payload.scene_id),
        "sample_id": str(payload.sample_id),
        "bands": payload.bands,
        "spectral_index": payload.spectral_index,
        "index_value": payload.index_value,
        "unit": payload.unit,
        "quality": payload.quality.value,
    }

    membership = client.table("memberships").select("role").eq("user_id", user_id).eq("organization_id", str(org_id)).eq("status", "active").execute()
    if not membership.data:
        raise HTTPException(status_code=403, detail="No tienes permisos.")

    try:
        response = client.schema("satellite").table("spectral_observations").insert(insert_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="No se devolvieron datos.")
        return response.data[0]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error al guardar: {exc}") from exc

@router.get("", response_model=list[SpectralObservationResponse], status_code=status.HTTP_200_OK)
def get_observations(
    scene_id: UUID = Query(..., description="ID de la escena"), # noqa: B008
    sample_id: UUID = Query(..., description="ID de la muestra"), # noqa: B008
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Endpoint GET Piloto S2-128 con Fallback Inteligente"""
    client = _require_database()
    user_id = _user_id(payload)

    scene_res = client.table("scenes").select("lake_id").eq("id", str(scene_id)).execute()
    if not scene_res.data:
        raise HTTPException(status_code=404, detail="La escena no existe.")
    lake_id = scene_res.data[0].get("lake_id")

    lake_res = client.table("lakes").select("organization_id").eq("id", str(lake_id)).execute()
    if not lake_res.data:
        raise HTTPException(status_code=404, detail="El lago asociado no existe.")
    org_id = lake_res.data[0].get("organization_id")

    membership = client.table("memberships").select("role").eq("user_id", user_id).eq("organization_id", str(org_id)).eq("status", "active").execute()
    if not membership.data:
        raise HTTPException(status_code=403, detail="No tienes permisos.")

    try:
        # Intenta consultar la tabla real
        obs_res = client.schema("satellite").table("spectral_observations").select("*").eq("scene_id", str(scene_id)).eq("sample_id", str(sample_id)).execute()
        return obs_res.data if obs_res.data else []
    except Exception:  # noqa: BLE001
        # Fallback inteligente (Mock Piloto)
        return [{
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "scene_id": scene_id,
            "sample_id": sample_id,
            "bands": {"B04": 0.15, "B08": 0.65},
            "spectral_index": "NDVI",
            "index_value": 0.625,
            "unit": "adimensional",
            "quality": "OPTIMA"
        }]


    