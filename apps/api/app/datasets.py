from fastapi import APIRouter, HTTPException

from catalog.application.schemas import (
    DatasetCandidateBase,
    DatasetCandidateResponse,
    DatasetDecisionCreate,
    DatasetManifestBase,
    DatasetManifestResponse,
    DatasetVersionBase,
    DatasetVersionResponse,
)

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])


@router.post("/candidates", response_model=DatasetCandidateResponse, status_code=201)
async def create_candidate(payload: DatasetCandidateBase):
    """Registra un nuevo dataset candidato."""
    raise HTTPException(status_code=501, detail="Endpoint en construcción (S2-105)")


@router.post("/decisions", response_model=dict, status_code=201)
async def create_decision(payload: DatasetDecisionCreate):
    """Registra la decisión sobre un candidato."""
    raise HTTPException(status_code=501, detail="Endpoint en construcción (S2-105)")


@router.post("/versions", response_model=DatasetVersionResponse, status_code=201)
async def create_version(payload: DatasetVersionBase):
    """Genera una nueva versión de dataset."""
    raise HTTPException(status_code=501, detail="Endpoint en construcción (S2-105)")


@router.post("/manifests", response_model=DatasetManifestResponse, status_code=201)
async def create_manifest(payload: DatasetManifestBase):
    """Registra el manifiesto de una versión."""
    raise HTTPException(status_code=501, detail="Endpoint en construcción (S2-105)")
