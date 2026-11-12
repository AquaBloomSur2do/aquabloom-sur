import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from httpx import HTTPError
from storage3.utils import StorageException

from apps.api.app.domains.dataset.domain_dataset import (
    APPROVAL_ROLES,
    MAX_TRAINING_FILE_SIZE,
    READ_ROLES,
    TRAINING_VARIABLES,
    build_default_training_csv_bytes,
    generate_deterministic_checksum,
    is_state_transition_allowed,
    is_version_immutable,
)
from apps.api.app.domains.dataset.model_dataset import (
    APIError,
    fetch_manifest_observations_with_fallback,
    fetch_manifest_samples_with_fallback,
    fetch_manifest_sources_with_fallback,
    fetch_page_rows,
    fetch_rows,
    raise_publication_database_error,
)
from apps.api.app.domains.dataset.schemas_dataset import (
    DatasetDecisionInput,
    DatasetManifest,
    DatasetVersionStateUpdate,
    IncorporateCandidatesInput,
    ManifestItem,
    ManifestRule,
    VersionState,
)

logger = logging.getLogger(__name__)


def extract_valid_user_id(payload: dict) -> str:
    user_id = payload.get("sub")
    try:
        return str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin un identificador de usuario válido.",
        ) from exc


def validate_state_transition(
    current_state: VersionState, target_state: VersionState
) -> None:
    if not is_state_transition_allowed(current_state, target_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Transición de estado no permitida desde '{current_state.value}' "
                f"hacia '{target_state.value}'."
            ),
        )


def list_review_datasets_service(
    client,
    *,
    user_id: str,
    page: int,
    page_size: int,
    version_page: int,
    version_page_size: int,
    membership_page: int,
    membership_page_size: int,
    decision_page: int,
    decision_page_size: int,
    org_membership_page: int,
    org_membership_page_size: int,
) -> dict:
    org_offset = (org_membership_page - 1) * org_membership_page_size
    active_memberships, has_more_org_memberships = fetch_page_rows(
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

    offset = (page - 1) * page_size
    datasets, has_more_datasets = fetch_page_rows(
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

    version_offset = (version_page - 1) * version_page_size
    versions, has_more_versions = fetch_page_rows(
        client.schema("dataset")
        .table("versions")
        .select("id, dataset_id, version_number, state, status, created_at")
        .in_("dataset_id", list(datasets_by_id))
        .range(version_offset, version_offset + version_page_size),
        version_page_size,
    )
    versions_by_id: dict[str, dict] = {}
    for version in versions:
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

    membership_offset = (membership_page - 1) * membership_page_size
    memberships, has_more_memberships = fetch_page_rows(
        client.schema("dataset")
        .table("memberships")
        .select("id, version_id, scene_provider, scene_external_id, added_at")
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

    has_more_decisions = False
    if memberships_by_id:
        decision_offset = (decision_page - 1) * decision_page_size
        decisions, has_more_decisions = fetch_page_rows(
            client.schema("dataset")
            .table("decisions")
            .select("id, membership_id, decision, reason, decided_by, decided_at")
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


def publish_dataset_version_service(client, version_id: UUID, user_id: str) -> dict:
    dataset_client = client.schema("dataset")

    try:
        version_rows = fetch_rows(
            dataset_client.table("versions")
            .select("id, dataset_id, version_number, status, created_at, published_at")
            .eq("id", str(version_id))
            .limit(1)
        )
    except APIError as exc:
        raise_publication_database_error(exc)

    if not version_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión del dataset no existe.",
        )

    version = version_rows[0]
    if version["status"] == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede publicar una versión archivada.",
        )

    try:
        dataset_rows = fetch_rows(
            dataset_client.table("datasets")
            .select("id, organization_id")
            .eq("id", version["dataset_id"])
            .limit(1)
        )
    except APIError as exc:
        raise_publication_database_error(exc)

    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El dataset asociado no existe.",
        )

    try:
        organization_memberships = fetch_rows(
            client.table("memberships")
            .select("role")
            .eq("user_id", user_id)
            .eq("organization_id", dataset_rows[0]["organization_id"])
            .eq("status", "active")
        )
    except APIError as exc:
        raise_publication_database_error(exc)

    if not any(
        str(membership.get("role", "")).strip().lower() in APPROVAL_ROLES
        for membership in organization_memberships
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para publicar esta versión.",
        )

    if version["status"] != "published":
        publication_time = datetime.now(UTC)
        try:
            updated_rows = fetch_rows(
                dataset_client.table("versions")
                .update(
                    {
                        "status": "published",
                        "published_at": publication_time.isoformat(),
                    }
                )
                .eq("id", str(version_id))
            )
        except APIError as exc:
            raise_publication_database_error(exc)

        if not updated_rows:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="La versión no se actualizó al publicarla.",
            )
        version = updated_rows[0]

    return version


def create_membership_decision_service(
    client,
    membership_id: UUID,
    decision_input: DatasetDecisionInput,
    user_id: str,
) -> dict:
    dataset_client = client.schema("dataset")

    membership_rows = fetch_rows(
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

    version_rows = fetch_rows(
        dataset_client.table("versions")
        .select("id, dataset_id, state, status")
        .eq("id", membership_rows[0]["version_id"])
        .limit(1)
    )
    if not version_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión del dataset no existe.",
        )

    version_data = version_rows[0]
    raw_state = str(
        version_data.get("state") or version_data.get("status") or "DRAFT"
    ).upper()
    if is_version_immutable(raw_state):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"No se pueden registrar decisiones en una versión inmutable ({raw_state}). "
                "Debe generar una nueva versión."
            ),
        )

    dataset_rows = fetch_rows(
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
    membership_data = fetch_rows(
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
            detail="No tienes permisos para registrar decisiones en este dataset.",
        )

    inserted = fetch_rows(
        dataset_client.table("decisions").insert(
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


def incorporate_candidates_service(
    client,
    version_id: UUID,
    input_data: IncorporateCandidatesInput,
    user_id: str,
) -> dict:
    dataset_client = client.schema("dataset")

    if not input_data.candidate_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista de IDs de candidatos no puede estar vacía.",
        )

    version_rows = fetch_rows(
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
    raw_state = str(
        version_data.get("state") or version_data.get("status") or "DRAFT"
    ).upper()

    if is_version_immutable(raw_state):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"No se pueden añadir candidatos a una versión inmutable ({raw_state}). "
                "Debe generar una nueva versión."
            ),
        )

    dataset_id = version_data["dataset_id"]

    dataset_rows = fetch_rows(
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

    organization_memberships = fetch_rows(
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
            detail="No tienes permisos para incorporar candidatos en este dataset.",
        )

    records_to_insert = [
        {
            "version_id": str(version_id),
            "scene_external_id": str(cid),
        }
        for cid in input_data.candidate_ids
    ]

    try:
        inserted = fetch_rows(
            dataset_client.table("memberships").insert(records_to_insert)
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


def update_version_state_service(
    client,
    version_id: UUID,
    state_input: DatasetVersionStateUpdate,
    user_id: str,
) -> dict:
    dataset_client = client.schema("dataset")

    version_rows = fetch_rows(
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

    dataset_rows = fetch_rows(
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

    organization_memberships = fetch_rows(
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
            detail="No tienes permisos para modificar el estado de esta versión.",
        )

    new_state_str = state_input.state.value

    updated_rows = fetch_rows(
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

    if new_state_str == "PUBLISHED":
        manifest_exists = fetch_rows(
            dataset_client.table("training_manifests")
            .select("id")
            .eq("version_id", str(version_id))
            .limit(1)
        )
        if not manifest_exists:
            csv_bytes, checksum = build_default_training_csv_bytes()

            if len(csv_bytes) > MAX_TRAINING_FILE_SIZE:
                fetch_rows(
                    dataset_client.table("versions")
                    .update({"state": raw_state, "status": raw_state})
                    .eq("id", str(version_id))
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="El archivo de entrenamiento supera el límite de 1 MiB.",
                )

            storage_path = f"versions/{version_id}/training.csv"

            try:
                client.storage.from_("training_files").upload(
                    storage_path,
                    csv_bytes,
                    file_options={
                        "content-type": "text/csv; charset=utf-8",
                        "upsert": "true",
                    },
                )
            except Exception as exc:
                fetch_rows(
                    dataset_client.table("versions")
                    .update({"state": raw_state, "status": raw_state})
                    .eq("id", str(version_id))
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="No se pudo almacenar el archivo de entrenamiento.",
                ) from exc

            try:
                manifest_rows = fetch_rows(
                    dataset_client.table("training_manifests").insert(
                        {
                            "version_id": str(version_id),
                            "storage_path": storage_path,
                            "checksum": checksum,
                        }
                    )
                )
                if not manifest_rows:
                    raise RuntimeError("Fallo inserción vacía en BD.")
            except Exception as exc:
                try:
                    client.storage.from_("training_files").remove([storage_path])
                except (HTTPError, StorageException) as cleanup_exc:
                    logger.warning(
                        f"No se pudo limpiar el archivo parcial de Storage: {cleanup_exc}"
                    )

                fetch_rows(
                    dataset_client.table("versions")
                    .update(
                        {
                            "state": raw_state,
                            "status": raw_state,
                            "published_at": None,
                        }
                    )
                    .eq("id", str(version_id))
                )

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No se pudo registrar el manifiesto de entrenamiento. Transacción revertida.",
                ) from exc

    return updated_rows[0]


def validate_training_file_access(
    version_id: UUID, user_id: str, client, dataset_schema
) -> dict:
    version_rows = fetch_rows(
        dataset_schema.table("versions")
        .select("id, dataset_id, state")
        .eq("id", str(version_id))
        .limit(1)
    )
    if not version_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Versión no encontrada."
        )

    if str(version_rows[0].get("state", "")).upper() != "PUBLISHED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La versión no está publicada.",
        )

    dataset_rows = fetch_rows(
        dataset_schema.table("datasets")
        .select("organization_id")
        .eq("id", version_rows[0]["dataset_id"])
        .limit(1)
    )
    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado."
        )

    membership = fetch_rows(
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("organization_id", dataset_rows[0]["organization_id"])
        .eq("status", "active")
    )
    if (
        not membership
        or str(membership[0].get("role", "")).strip().lower() not in READ_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para esta organización.",
        )

    manifest_rows = fetch_rows(
        dataset_schema.table("training_manifests")
        .select("id, storage_path, checksum, variables")
        .eq("version_id", str(version_id))
        .limit(1)
    )
    if not manifest_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="El manifiesto no existe."
        )

    manifest = manifest_rows[0]
    if manifest.get("variables") != TRAINING_VARIABLES:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Las variables del manifiesto de entrenamiento no son válidas.",
        )
    if (
        not isinstance(manifest.get("checksum"), str)
        or len(manifest["checksum"]) != 64
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="El checksum del manifiesto de entrenamiento no es válido.",
        )

    return manifest


def download_and_verify_training_bytes(client, manifest: dict) -> bytes:
    try:
        file_bytes = client.storage.from_("training_files").download(
            manifest["storage_path"]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al descargar el archivo físico.",
        ) from exc

    if len(file_bytes) > MAX_TRAINING_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El archivo de entrenamiento supera el límite permitido.",
        )
    if hashlib.sha256(file_bytes).hexdigest() != manifest["checksum"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El checksum del archivo de entrenamiento no coincide con el manifiesto.",
        )
    return file_bytes


def build_version_manifest_service(
    client, dataset_id: UUID, version_id: str
) -> DatasetManifest:
    raw_sources = fetch_manifest_sources_with_fallback(client)
    raw_obs = fetch_manifest_observations_with_fallback(client)
    raw_records = fetch_manifest_samples_with_fallback(client)

    raw_rules = [
        {"id": "rule-01", "description": "Filtro de cobertura de nubes máxima 20%"},
        {"id": "rule-02", "description": "Validación de rango de clorofila-a [0-100]"},
    ]

    sources = [
        ManifestItem(
            id=str(src["id"]), checksum=generate_deterministic_checksum(src)
        )
        for src in raw_sources
    ]
    observations = [
        ManifestItem(
            id=str(obs["id"]), checksum=generate_deterministic_checksum(obs)
        )
        for obs in raw_obs
    ]
    records = [
        ManifestItem(
            id=str(rec["id"]), checksum=generate_deterministic_checksum(rec)
        )
        for rec in raw_records
    ]
    rules = [
        ManifestRule(
            id=str(rl["id"]),
            description=rl["description"],
            checksum=generate_deterministic_checksum(rl),
        )
        for rl in raw_rules
    ]

    manifest_payload = {
        "dataset_id": str(dataset_id),
        "version_id": version_id,
        "records": [r.model_dump() for r in records],
        "sources": [s.model_dump() for s in sources],
        "observations": [o.model_dump() for o in observations],
        "rules": [r.model_dump() for r in rules],
    }

    global_checksum = generate_deterministic_checksum(manifest_payload)

    return DatasetManifest(
        dataset_id=str(dataset_id),
        version_id=version_id,
        records=records,
        sources=sources,
        observations=observations,
        rules=rules,
        manifest_checksum=global_checksum,
    )
