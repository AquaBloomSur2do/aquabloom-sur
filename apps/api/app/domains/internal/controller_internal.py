from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from apps.api.app.core.database import supabase
from apps.api.app.core.dependencies import require_internal_service
from apps.api.app.domains.dataset.schemas_dataset import DatasetProvenance
from apps.api.app.domains.dataset.service_dataset import (
    download_and_verify_training_bytes,
    get_dataset_provenance_for_training,
    get_dataset_version_for_training,
    validate_training_file_access,
)
from apps.api.app.domains.identity.model_identity import (
    get_active_organization_membership,
)
from apps.api.app.domains.identity.service_identity import get_current_user_profile

router = APIRouter(prefix="/internal/v1", tags=["Internal"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


@router.get("/users/{user_id}/profile")
def get_user_profile(
    user_id: UUID,
    email: str | None = Query(default=None),
    _token: None = Depends(require_internal_service),
):
    return get_current_user_profile(_require_database(), user_id, email)


@router.get("/organizations/{organization_id}/memberships/{user_id}")
def get_user_organization_membership(
    organization_id: UUID,
    user_id: UUID,
    _token: None = Depends(require_internal_service),
):
    return get_active_organization_membership(
        _require_database(), user_id, organization_id
    )


@router.get("/datasets/versions/{version_id}")
def get_training_dataset_version(
    version_id: UUID,
    organization_id: UUID,
    _token: None = Depends(require_internal_service),
):
    version = get_dataset_version_for_training(
        _require_database(), version_id, organization_id
    )
    if version is None or str(version.get("state", "")).upper() != "PUBLISHED":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Versión publicada no encontrada para la organización.",
        )
    return version


@router.get(
    "/datasets/versions/{version_id}/provenance",
    response_model=DatasetProvenance,
)
def get_training_dataset_provenance(
    version_id: UUID,
    organization_id: UUID,
    _token: None = Depends(require_internal_service),
):
    provenance = get_dataset_provenance_for_training(
        _require_database(), version_id, organization_id
    )
    if provenance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Versión publicada no encontrada para la organización.",
        )
    return provenance


@router.get("/datasets/versions/{version_id}/training-file/download")
def download_training_file(
    version_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    _token: None = Depends(require_internal_service),
):
    client = _require_database()
    manifest = validate_training_file_access(
        version_id,
        str(user_id),
        client,
        client.schema("dataset"),
        organization_id=organization_id,
    )
    file_bytes = download_and_verify_training_bytes(client, manifest)
    return Response(
        content=file_bytes,
        media_type="text/csv",
        headers={"X-Training-Checksum": manifest["checksum"]},
    )
