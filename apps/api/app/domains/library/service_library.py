from typing import Any
from uuid import UUID

from apps.api.app.domains.library.domain_library import (
    LIBRARY_STORAGE_BUCKET,
    build_library_storage_path,
    compute_library_file_checksum,
    validate_library_checksum,
    verify_library_file_integrity,
)
from apps.api.app.domains.library.model_library import (
    download_library_file_from_storage,
    upload_library_file_to_storage,
)


def store_library_file_with_checksum(
    client: Any,
    *,
    resource_id: UUID | str,
    version_id: UUID | str,
    filename: str,
    content: bytes,
    content_type: str = "text/csv",
    expected_checksum: str | None = None,
    bucket: str = LIBRARY_STORAGE_BUCKET,
) -> dict[str, Any]:
    """Calcula/valida el SHA-256, sube el archivo a Storage y devuelve su referencia."""
    checksum = compute_library_file_checksum(content)
    if expected_checksum is not None:
        normalized_expected = validate_library_checksum(expected_checksum)
        if checksum != normalized_expected:
            raise ValueError(
                "El checksum SHA-256 calculado no coincide con el checksum esperado."
            )

    storage_path = build_library_storage_path(resource_id, version_id, filename)
    upload_library_file_to_storage(
        client,
        storage_path,
        content,
        content_type=content_type,
        bucket=bucket,
    )
    return {
        "bucket": bucket,
        "storage_path": storage_path,
        "filename": filename.strip(),
        "content_type": content_type,
        "size_bytes": len(content),
        "checksum": checksum,
    }


def retrieve_and_verify_library_file(
    client: Any,
    *,
    storage_path: str,
    expected_checksum: str,
    bucket: str = LIBRARY_STORAGE_BUCKET,
) -> bytes:
    """Recupera los bytes desde Storage y verifica que coincidan con el checksum."""
    normalized_expected = validate_library_checksum(expected_checksum)
    recovered_bytes = download_library_file_from_storage(
        client,
        storage_path,
        bucket=bucket,
    )
    if not verify_library_file_integrity(recovered_bytes, normalized_expected):
        raise ValueError(
            "Los bytes recuperados de Storage no coinciden con el checksum registrado."
        )
    return recovered_bytes
