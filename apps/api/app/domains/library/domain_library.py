from typing import Any
from uuid import UUID

from apps.api.app.domains.library.schemas_library import (
    LibraryAttribution,
    LibraryVersionCreate,
)


def validate_library_attribution(
    attribution: LibraryAttribution,
) -> dict[str, Any]:
    """Valida y serializa la atribucion preservando license (incluso null) y source."""
    if not attribution.source.name.strip():
        raise ValueError("La procedencia (source.name) es obligatoria.")
    serialized = attribution.model_dump(mode="json")
    if "license" not in serialized or "source" not in serialized:
        raise ValueError("La atribución debe incluir license y source.")
    return serialized


def build_library_version_record(
    payload: LibraryVersionCreate,
    user_id: str | None,
) -> dict[str, Any]:
    """Construye el registro persistible de una version de biblioteca."""
    attribution_data = validate_library_attribution(payload.attribution)
    record: dict[str, Any] = {
        "resource_id": str(payload.resource_id),
        "status": "draft",
        "attribution": attribution_data,
    }
    if user_id:
        record["created_by"] = str(UUID(str(user_id)))
    return record
