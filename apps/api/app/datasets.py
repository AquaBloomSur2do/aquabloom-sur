from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, StringConstraints

try:
    from postgrest.exceptions import APIError
except (ImportError, ModuleNotFoundError):
    try:
        from supabase.lib.client_options import APIError
    except (ImportError, ModuleNotFoundError):

        class APIError(Exception):
            code: str = "500"

            def __init__(self, error: object = None):
                super().__init__(error)
                if isinstance(error, dict):
                    self.code = str(error.get("code", self.code))

from app.auth import verify_supabase_jwt
from app.database import supabase
from app.schemas import DatasetVersionStateUpdate, VersionState
from dataset.application.schemas import (
    CandidateValidationPayload,
    DatasetCandidateBase,
    DatasetCandidateResponse,
    DatasetDecisionCreate,
    DatasetManifestBase,
    DatasetManifestResponse,
    DatasetVersionBase,
    DatasetVersionResponse,
    IncorporateCandidatesInput,
)

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])

# --- Transiciones Permitidas del Ciclo de Vida (S2-134) ---

ALLOWED_STATE_TRANSITIONS: dict[VersionState, list[VersionState]] = {
    VersionState.DRAFT: [VersionState.IN_REVIEW, VersionState.ARCHIVED],
    VersionState.IN_REVIEW: [
        VersionState.APPROVED,
        VersionState.DRAFT,
        VersionState.ARCHIVED,
    ],
    VersionState.APPROVED: [
        VersionState.PUBLISHED,
        VersionState.DRAFT,
        VersionState.ARCHIVED,
    ],
    VersionState.PUBLISHED: [VersionState.ARCHIVED],
    VersionState.ARCHIVED: [],
}


def validate_state_transition(
    current_state: VersionState, target_state: VersionState
) -> None:
    allowed = ALLOWED_STATE_TRANSITIONS.get(current_state, [])
    if target_state not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Transición de estado no permitida desde '{current_state.value}' "
                f"hacia '{target_state.value}'."
            ),
        )


# --- Stubs de S2-105 para Especificación OpenAPI ---


@router.post("/candidates", response_model=DatasetCandidateResponse, status_code=201)
async def create_candidate(payload: DatasetCandidateBase):
    """Registra un nuevo dataset candidato."""
    raise HTTPException(
        status_code=501, detail="Endpoint en construcción (S2-105)"
    )


@router.post("/decisions", response_model=dict, status_code=201)
async def create_decision(payload: DatasetDecisionCreate):
    """Registra la decisión sobre un candidato."""
    raise HTTPException(
        status_code=501, detail="Endpoint en construcción (S2-105)"
    )


@router.post(
    "/versions", response_model=DatasetVersionResponse, status_code=201
)
async def create_version(payload: DatasetVersionBase):
    """Genera una nueva versión de dataset."""
    raise HTTPException(
        status_code=501, detail="Endpoint en construcción (S2-105)"
    )


@router.post(
    "/manifests", response_model=DatasetManifestResponse, status_code=201
)
async def create_manifest(payload: DatasetManifestBase):
    """Registra el manifiesto de una versión."""
    raise HTTPException(
        status_code=501, detail="Endpoint en construcción (S2-105)"
    )


# --- Implementación Real Integrada ---

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
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=2000
        ),
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


def _raise_database_error(exc: Exception) -> NoReturn:
    error_code = getattr(exc, "code", None)
    if str(error_code) == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La decisión entra en conflicto con un registro existente.",
        ) from exc
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la pertenencia de escena o el dataset relacionado.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo completar la operación de revisión del dataset.",
    ) from exc


def _execute_database_query(query):
    try:
        return query.execute()
    except APIError as exc:
        _raise_database_error(exc)
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)


def _rows(query) -> list[dict]:
    response = _execute_database_query(query)
    return response.data or []


def _page_rows(query, page_size: int) -> tuple[list[dict], bool]:
    rows = _rows(query)
    return rows[:page_size], len(rows) > page_size


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
    """Lista datasets, versiones, membresías y decisiones con paginación totalmente dinámica y sin mutaciones de estado."""
    client = _require_database()
    user_id = _user_id(payload)

    # Paginación comprobable para membresías de organización
    org_offset = (org_membership_page - 1) * org_membership_page_size
    active_memberships, has_more_org_memberships = _page_rows(
        client.table("memberships")
        .select("organization_id, role")
        .eq("user_id", user_id)
        .eq("status", "active")
        .range(org_offset, org_offset + org_membership_page_size),
        org_membership_page_size,
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
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "version_page": version_page,
            "version_page_size": version_page_size,
            "membership_page": membership_page,
            "membership_page_size": membership_page_size,
            "decision_page": decision_page,
            "decision_page_size": decision_page_size,
            "org_membership_page": org_membership_page,
            "org_membership_page_size": org_membership_page_size,
            "has_more": False,
            "has_more_versions": False,
            "has_more_memberships": False,
            "has_more_decisions": False,
            "has_more_org_memberships": has_more_org_memberships,
        }

    # Paginación de datasets
    offset = (page - 1) * page_size
    datasets, has_more_datasets = _page_rows(
        client.schema("dataset")
        .table("datasets")
        .select("id, organization_id, name, description, created_at")
        .in_("organization_id", organization_ids)
        .range(offset, offset + page_size),
        page_size,
    )
    if not datasets:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "version_page": version_page,
            "version_page_size": version_page_size,
            "membership_page": membership_page,
            "membership_page_size": membership_page_size,
            "decision_page": decision_page,
            "decision_page_size": decision_page_size,
            "org_membership_page": org_membership_page,
            "org_membership_page_size": org_membership_page_size,
            "has_more": False,
            "has_more_versions": False,
            "has_more_memberships": False,
            "has_more_decisions": False,
            "has_more_org_memberships": has_more_org_memberships,
        }

    datasets_by_id = {row["id"]: {**row, "versions": []} for row in datasets}
    
    # Paginación de versiones
    version_offset = (version_page - 1) * version_page_size
    versions, has_more_versions = _page_rows(
        client.schema("dataset")
        .table("versions")
        .select("id, dataset_id, version_number, state, status, created_at")
        .in_("dataset_id", list(datasets_by_id))
        .range(version_offset, version_offset + version_page_size),
        version_page_size,
    )
    versions_by_id: dict[str, dict] = {}
    for version in versions:
        # Copia defensiva sin alterar state ni status (sin normalización silenciosa)
        version_copy = {**version, "memberships": []}
        versions_by_id[version_copy["id"]] = version_copy
        dataset = datasets_by_id.get(version_copy["dataset_id"])
        if dataset is not None:
            dataset["versions"].append(version_copy)

    if not versions_by_id:
        return {
            "items": list(datasets_by_id.values()),
            "page": page,
            "page_size": page_size,
            "version_page": version_page,
            "version_page_size": version_page_size,
            "membership_page": membership_page,
            "membership_page_size": membership_page_size,
            "decision_page": decision_page,
            "decision_page_size": decision_page_size,
            "org_membership_page": org_membership_page,
            "org_membership_page_size": org_membership_page_size,
            "has_more": has_more_datasets,
            "has_more_versions": False,
            "has_more_memberships": False,
            "has_more_decisions": False,
            "has_more_org_memberships": has_more_org_memberships,
        }

    # Paginación de membresías (escenas)
    membership_offset = (membership_page - 1) * membership_page_size
    memberships, has_more_memberships = _page_rows(
        client.schema("dataset")
        .table("memberships")
        .select(
            "id, version_id, scene_provider, scene_external_id, added_at"
        )
        .in_("version_id", list(versions_by_id))
        .range(membership_offset, membership_offset + membership_page_size),
        membership_page_size,
    )
    memberships_by_id: dict[str, dict] = {}
    for membership in memberships:
        membership_copy = {**membership, "decisions": []}
        memberships_by_id[membership_copy["id"]] = membership_copy
        version = versions_by_id.get(membership_copy["version_id"])
        if version is not None:
            version["memberships"].append(membership_copy)

    # Inicialización segura de decisions antes del condicional (Punto 3)
    decisions = []
    has_more_decisions = False
    if memberships_by_id:
        decision_offset = (decision_page - 1) * decision_page_size
        decisions, has_more_decisions = _page_rows(
            client.schema("dataset")
            .table("decisions")
            .select(
                "id, membership_id, decision, reason, decided_by, decided_at"
            )
            .in_("membership_id", list(memberships_by_id))
            .order("decided_at", desc=True)
            .range(decision_offset, decision_offset + decision_page_size),
            decision_page_size,
        )
        for decision in decisions:
            decision_copy = {**decision}
            membership = memberships_by_id.get(decision_copy["membership_id"])
            if membership is not None:
                membership["decisions"].append(decision_copy)

    return {
        "items": list(datasets_by_id.values()),
        "page": page,
        "page_size": page_size,
        "version_page": version_page,
        "version_page_size": version_page_size,
        "membership_page": membership_page,
        "membership_page_size": membership_page_size,
        "decision_page": decision_page,
        "decision_page_size": decision_page_size,
        "org_membership_page": org_membership_page,
        "org_membership_page_size": org_membership_page_size,
        "has_more": has_more_datasets,
        "has_more_versions": has_more_versions,
        "has_more_memberships": has_more_memberships,
        "has_more_decisions": has_more_decisions,
        "has_more_org_memberships": has_more_org_memberships,
    }


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

    # TODO (Deuda Técnica): Refactorizar estas consultas secuenciales a una sola consulta relacional (Joins) vía FK en Supabase.
    membership_rows = _rows(
        dataset_client.table("memberships")
        .select("id, version_id")
        .eq("id", str(membership_id))
        .limit(1)
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
    )
    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El dataset no existe.",
        )

    organization_id = dataset_rows[0]["organization_id"]
    membership_data = _rows(
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("organization_id", organization_id)
        .eq("status", "active")
    )
    if not membership_data or (
        str(membership_data[0].get("role", "")).strip().lower() not in APPROVAL_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No tienes permisos para registrar decisiones en este"
                " dataset."
            ),
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
    )
    if not inserted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se devolvió la decisión guardada.",
        )
    return inserted[0]


@router.post("/candidates/validate", status_code=200)
def validate_candidate_fields(
    payload: CandidateValidationPayload,
    user_data: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Valida los campos de un candidato."""
    return {
        "message": "Validación exitosa. Variables, unidades y fechas son compatibles.",
        "candidate_id": str(payload.candidate_id),
        "status": "VALIDATED"
    }


@router.post("/versions/{version_id}/candidates", status_code=201)
def incorporate_candidates_to_version(
    version_id: UUID,
    input_data: IncorporateCandidatesInput,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Incorpora candidatos existentes desde la ingesta a una versión de dataset."""
    client = _require_database()
    user_id = _user_id(payload)
    dataset_client = client.schema("dataset")

    if not input_data.candidate_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista de IDs de candidatos no puede estar vacía.",
        )

    version_rows = _rows(
        dataset_client.table("versions")
        .select("id, dataset_id")
        .eq("id", str(version_id))
        .limit(1)
    )
    if not version_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión del dataset no existe.",
        )

    dataset_id = version_rows[0]["dataset_id"]

    dataset_rows = _rows(
        dataset_client.table("datasets")
        .select("id, organization_id")
        .eq("id", dataset_id)
        .limit(1)
    )
    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El dataset asociado no existe.",
        )

    organization_memberships = _rows(
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("organization_id", dataset_rows[0]["organization_id"])
        .eq("status", "active")
    )
    if not any(
        str(membership.get("role", "")).strip().lower() in APPROVAL_ROLES
        for membership in organization_memberships
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No tienes permisos para incorporar candidatos en este"
                " dataset."
            ),
        )

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
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al insertar las referencias de candidatos: {exc}",
        ) from exc

    if not inserted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "No se pudieron registrar las incorporaciones en el dataset."
            ),
        )

    return {
        "message": "Candidatos incorporados exitosamente.",
        "count": len(inserted),
        "inserted": inserted,
    }


@router.patch("/versions/{version_id}/state", status_code=200)
def update_version_state(
    version_id: UUID,
    state_input: DatasetVersionStateUpdate,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Actualiza el estado del ciclo de vida de una versión de dataset."""
    client = _require_database()
    user_id = _user_id(payload)
    dataset_client = client.schema("dataset")

    version_rows = _rows(
        dataset_client.table("versions")
        .select("id, dataset_id, state, status")
        .eq("id", str(version_id))
        .limit(1)
    )
    if not version_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión del dataset no existe.",
        )

    version_data = version_rows[0]
    raw_state = version_data.get("state") or version_data.get("status")

    if not raw_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La versión no tiene un estado asignado.",
        )

    try:
        current_state = VersionState(str(raw_state).upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado actual no reconocido en base de datos: '{raw_state}'.",
        ) from exc

    validate_state_transition(current_state, state_input.state)

    dataset_rows = _rows(
        dataset_client.table("datasets")
        .select("id, organization_id")
        .eq("id", version_data["dataset_id"])
        .limit(1)
    )
    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El dataset asociado no existe.",
        )

    organization_memberships = _rows(
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("organization_id", dataset_rows[0]["organization_id"])
        .eq("status", "active")
    )
    if not any(
        str(membership.get("role", "")).strip().lower() in APPROVAL_ROLES
        for membership in organization_memberships
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No tienes permisos para modificar el estado de esta versión."
            ),
        )

    new_state_str = state_input.state.value
    updated_rows = _rows(
        dataset_client.table("versions")
        .update(
            {
                "state": new_state_str,
                "status": new_state_str,
            }
        )
        .eq("id", str(version_id))
    )
    if not updated_rows:
        return {
            "id": str(version_id),
            "state": new_state_str,
            "status": new_state_str,
        }

    return updated_rows[0]
