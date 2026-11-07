import csv
import hashlib
import io
import json

from apps.api.app.domains.dataset.schemas_dataset import VersionState

TRAINING_VARIABLES = ["temperatura", "clorofila_a", "turbidez", "ph"]
MAX_TRAINING_FILE_SIZE = 1024 * 1024

READ_ROLES = {
    "admin",
    "administrador",
    "supervisor",
    "investigador",
    "auditor",
}
APPROVAL_ROLES = {"admin", "administrador", "supervisor"}

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


def is_state_transition_allowed(
    current_state: VersionState, target_state: VersionState
) -> bool:
    allowed = ALLOWED_STATE_TRANSITIONS.get(current_state, [])
    return target_state in allowed


def is_version_immutable(raw_state: str | None) -> bool:
    state_upper = str(raw_state or "DRAFT").upper()
    return state_upper in {"PUBLISHED", "ARCHIVED"}


def generate_deterministic_checksum(data: dict) -> str:
    """Genera un SHA-256 determinístico basado en el contenido del diccionario."""
    serialized = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def build_default_training_csv_bytes() -> tuple[bytes, str]:
    """Construye el archivo CSV de entrenamiento piloto y su checksum SHA-256."""
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\r\n")
    writer.writerow(TRAINING_VARIABLES)
    writer.writerow(["15.5", "2.1", "0.5", "7.2"])

    csv_bytes = csv_buffer.getvalue().encode("utf-8")
    checksum = hashlib.sha256(csv_bytes).hexdigest()
    return csv_bytes, checksum
