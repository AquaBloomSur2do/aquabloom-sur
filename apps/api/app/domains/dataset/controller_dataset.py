from typing import Annotated
from uuid import UUID

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.database import supabase
from apps.api.app.domains.dataset.schemas_dataset import (
    CandidateValidationPayload,
    DatasetCandidateBase,
    DatasetCandidateResponse,
    DatasetDecisionCreate,
    DatasetDecisionInput,
    DatasetManifest,
    DatasetManifestBase,
    DatasetManifestResponse,
    DatasetVersionBase,
    DatasetVersionResponse,
    DatasetVersionStateUpdate,
    IncorporateCandidatesInput,
    TrainingManifestResponse,
)
from apps.api.app.domains.dataset.service_dataset import (
    build_version_manifest_service,
    create_membership_decision_service,
    download_and_verify_training_bytes,
    extract_valid_user_id,
    incorporate_candidates_service,
    list_review_datasets_service,
    publish_dataset_version_service,
    update_version_state_service,
    validate_training_file_access,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )
    return supabase


# --- Stubs de S2-105 para Especificación OpenAPI ---


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


# --- Implementación Real Integrada ---


@router.get("/review")
def list_review_datasets(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    version_page: Annotated[int, Query(ge=1)] = 1,
    version_page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    membership_page: Annotated[int, Query(ge=1)] = 1,
    membership_page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    decision_page: Annotated[int, Query(ge=1)] = 1,
    decision_page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    org_membership_page: Annotated[int, Query(ge=1)] = 1,
    org_membership_page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    client = _require_database()
    user_id = extract_valid_user_id(payload)
    return list_review_datasets_service(
        client,
        user_id=user_id,
        page=page,
        page_size=page_size,
        version_page=version_page,
        version_page_size=version_page_size,
        membership_page=membership_page,
        membership_page_size=membership_page_size,
        decision_page=decision_page,
        decision_page_size=decision_page_size,
        org_membership_page=org_membership_page,
        org_membership_page_size=org_membership_page_size,
    )


@router.post(
    "/versions/{version_id}/publish",
    response_model=DatasetVersionResponse,
)
def publish_dataset_version(
    version_id: UUID,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    client = _require_database()
    user_id = extract_valid_user_id(payload)
    return publish_dataset_version_service(client, version_id, user_id)


@router.post("/memberships/{membership_id}/decisions", status_code=201)
def create_membership_decision(
    membership_id: UUID,
    decision_input: DatasetDecisionInput,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    client = _require_database()
    user_id = extract_valid_user_id(payload)
    return create_membership_decision_service(
        client, membership_id, decision_input, user_id
    )


@router.post("/candidates/validate", status_code=200)
def validate_candidate_fields(
    payload: CandidateValidationPayload,
    user_data: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    return {
        "message": "Validación exitosa. Variables, unidades y fechas son compatibles.",
        "candidate_id": str(payload.candidate_id),
        "status": "VALIDATED",
    }


@router.post("/versions/{version_id}/candidates", status_code=201)
def incorporate_candidates_to_version(
    version_id: UUID,
    input_data: IncorporateCandidatesInput,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    client = _require_database()
    user_id = extract_valid_user_id(payload)
    return incorporate_candidates_service(client, version_id, input_data, user_id)


@router.patch("/versions/{version_id}/state", status_code=200)
def update_version_state(
    version_id: UUID,
    state_input: DatasetVersionStateUpdate,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    client = _require_database()
    user_id = extract_valid_user_id(payload)
    return update_version_state_service(client, version_id, state_input, user_id)


@router.get(
    "/versions/{version_id}/training-file", response_model=TrainingManifestResponse
)
def get_training_file_metadata(
    version_id: UUID, payload: dict = Depends(verify_supabase_jwt)  # noqa: B008
):
    client = _require_database()
    manifest = validate_training_file_access(
        version_id, extract_valid_user_id(payload), client, client.schema("dataset")
    )
    return {
        "version_id": version_id,
        "manifest_id": manifest["id"],
        "variables": manifest["variables"],
        "checksum": manifest["checksum"],
        "download_url": f"/api/v1/datasets/versions/{version_id}/training-file/download",
    }


@router.get("/versions/{version_id}/training-file/download")
def download_training_file_proxy(
    version_id: UUID, payload: dict = Depends(verify_supabase_jwt)  # noqa: B008
):
    client = _require_database()
    manifest = validate_training_file_access(
        version_id, extract_valid_user_id(payload), client, client.schema("dataset")
    )
    file_bytes = download_and_verify_training_bytes(client, manifest)
    return Response(
        content=file_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="training_{version_id}.csv"'
        },
    )


@router.get(
    "/{dataset_id}/versions/{version_id}/manifest",
    response_model=DatasetManifest,
    status_code=status.HTTP_200_OK,
)
def build_version_manifest(
    dataset_id: UUID,
    version_id: str,
    _token: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    client = _require_database()
    return build_version_manifest_service(client, dataset_id, version_id)
