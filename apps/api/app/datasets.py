from typing import Annotated, Literal
from uuid import UUID

from dataset.application.schemas import (
    DatasetCandidateBase,
    DatasetCandidateResponse,
    DatasetDecisionCreate,
    DatasetManifestBase,
    DatasetManifestResponse,
    DatasetVersionBase,
    DatasetVersionResponse,
    IncorporateCandidatesInput,
)
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints

from app.auth import verify_supabase_jwt
from app.database import supabase

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])

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


# --- Implementación Real Integrada desde Main ---


router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])

READ_ROLES = {
    "admin",
    "administrador",
    "supervisor",
    "investigador",
    "auditor",
}
APPROVAL_ROLES = {"admin", "administrador", "supervisor"}


class DatasetDecisionInput(BaseModel):
    decision: Literal["accepted", "rejected"]
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )
    return supabase


def _user_id(payload: dict) -> str:
    user_id = payload.get("sub")
    try:
        return str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin un identificador de usuario válido.",
        ) from exc


def _rows(response) -> list[dict]:
    return response.data or []


@router.get("/review")
def list_review_datasets(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    """Lista datasets y escenas visibles para la organización del usuario."""
    client = _require_database()
    user_id = _user_id(payload)

    active_memberships = _rows(
        client.table("memberships")
        .select("organization_id, role")
        .eq("user_id", user_id)
        .eq("status", "active")
        .execute()
    )
    organization_ids = list(
        {
            membership["organization_id"]
            for membership in active_memberships
            if membership.get("organization_id")
            and str(membership.get("role", "")).strip().lower() in READ_ROLES
        }
    )
    if not organization_ids:
        return []

    datasets = _rows(
        client.schema("dataset")
        .table("datasets")
        .select("id, organization_id, name, description, created_at")
        .in_("organization_id", organization_ids)
        .execute()
    )
    if not datasets:
        return []

    datasets_by_id = {row["id"]: {**row, "versions": []} for row in datasets}
    versions = _rows(
        client.schema("dataset")
        .table("versions")
        .select("id, dataset_id, version_number, status, created_at")
        .in_("dataset_id", list(datasets_by_id))
        .execute()
    )
    versions_by_id: dict[str, dict] = {}
    for version in versions:
        version["memberships"] = []
        versions_by_id[version["id"]] = version
        dataset = datasets_by_id.get(version["dataset_id"])
        if dataset is not None:
            dataset["versions"].append(version)

    if not versions_by_id:
        return list(datasets_by_id.values())

    memberships = _rows(
        client.schema("dataset")
        .table("memberships")
        .select("id, version_id, scene_provider, scene_external_id, added_at")
        .in_("version_id", list(versions_by_id))
        .execute()
    )
    memberships_by_id: dict[str, dict] = {}
    for membership in memberships:
        membership["decisions"] = []
        memberships_by_id[membership["id"]] = membership
        version = versions_by_id.get(membership["version_id"])
        if version is not None:
            version["memberships"].append(membership)

    if memberships_by_id:
        decisions = _rows(
            client.schema("dataset")
            .table("decisions")
            .select("id, membership_id, decision, reason, decided_by, decided_at")
            .in_("membership_id", list(memberships_by_id))
            .order("decided_at", desc=True)
            .execute()
        )
        for decision in decisions:
            membership = memberships_by_id.get(decision["membership_id"])
            if membership is not None:
                membership["decisions"].append(decision)

    return list(datasets_by_id.values())


@router.post("/memberships/{membership_id}/decisions", status_code=201)
def create_membership_decision(
    membership_id: UUID,
    decision_input: DatasetDecisionInput,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Registra una decisión si el usuario es aprobador activo de la organización."""
    client = _require_database()
    user_id = _user_id(payload)
    dataset_client = client.schema("dataset")

    membership_rows = _rows(
        dataset_client.table("memberships")
        .select("id, version_id")
        .eq("id", str(membership_id))
        .limit(1)
        .execute()
    )
    if not membership_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La pertenencia de escena no existe.",
        )

    version_rows = _rows(
        dataset_client.table("versions")
        .select("id, dataset_id")
        .eq("id", membership_rows[0]["version_id"])
        .limit(1)
        .execute()
    )
    if not version_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión del dataset no existe.",
        )

    dataset_rows = _rows(
        dataset_client.table("datasets")
        .select("id, organization_id")
        .eq("id", version_rows[0]["dataset_id"])
        .limit(1)
        .execute()
    )
    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El dataset no existe.",
        )

    organization_memberships = _rows(
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("organization_id", dataset_rows[0]["organization_id"])
        .eq("status", "active")
        .execute()
    )
    if not any(
        str(membership.get("role", "")).strip().lower() in APPROVAL_ROLES
        for membership in organization_memberships
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para registrar decisiones en este dataset.",
        )

    inserted = _rows(
        dataset_client.table("decisions")
        .insert(
            {
                "membership_id": str(membership_id),
                "decision": decision_input.decision,
                "reason": decision_input.reason,
                "decided_by": user_id,
            }
        )
        .execute()
    )
    if not inserted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se devolvió la decisión guardada.",
        )
    return inserted[0]

@router.post("/versions/{version_id}/candidates", status_code=201)
def incorporate_candidates_to_version(
    version_id: UUID,
    input_data: IncorporateCandidatesInput,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Incorpora candidatos existentes desde la ingesta a una versión de dataset de forma explícita, sin alterar los originales."""
    client = _require_database()
    user_id = _user_id(payload)
    dataset_client = client.schema("dataset")

    if not input_data.candidate_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista de IDs de candidatos no puede estar vacía.",
        )

    # 1. Verificar que la versión del dataset existe
    version_rows = _rows(
        dataset_client.table("versions")
        .select("id, dataset_id")
        .eq("id", str(version_id))
        .limit(1)
        .execute()
    )
    if not version_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión del dataset no existe.",
        )

    dataset_id = version_rows[0]["dataset_id"]

    # 2. Obtener la organización del dataset para validar permisos
    dataset_rows = _rows(
        dataset_client.table("datasets")
        .select("id, organization_id")
        .eq("id", dataset_id)
        .limit(1)
        .execute()
    )
    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El dataset asociado no existe.",
        )

    # 3. Validar que el usuario tenga permisos (aprobador/admin)
    organization_memberships = _rows(
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("organization_id", dataset_rows[0]["organization_id"])
        .eq("status", "active")
        .execute()
    )
    if not any(
        str(membership.get("role", "")).strip().lower() in APPROVAL_ROLES
        for membership in organization_memberships
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para incorporar candidatos en este dataset.",
        )

    # 4. Inserción masiva explícita en memberships (sin alterar la ingesta)
    records_to_insert = [
        {
            "version_id": str(version_id),
            "scene_external_id": str(cid), 
        }
        for cid in input_data.candidate_ids
    ]

    try:
        inserted = _rows(
            dataset_client.table("memberships")
            .insert(records_to_insert)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al insertar las referencias de candidatos: {exc}",
        ) from exc

    if not inserted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudieron registrar las incorporaciones en el dataset.",
        )

    return {
        "message": "Candidatos incorporados exitosamente.",
        "count": len(inserted),
        "inserted": inserted,
    }
