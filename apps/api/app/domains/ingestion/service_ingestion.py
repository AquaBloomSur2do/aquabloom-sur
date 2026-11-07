from typing import Any, NoReturn

from fastapi import HTTPException, status

try:
    from postgrest.exceptions import APIError
except (ImportError, ModuleNotFoundError):
    try:
        from supabase.lib.client_options import APIError
    except (ImportError, ModuleNotFoundError):

        class APIError(Exception):
            code: str = "500"
            details: str = "Error genérico de BD"

            def __init__(self, error: object = None):
                super().__init__(error)
                if isinstance(error, dict):
                    self.code = str(error.get("code", self.code))
                    self.details = str(error.get("details", self.details))

from apps.api.app.domains.ingestion.domain_ingestion import (
    compute_content_checksum,
    sanitize_upload_filename,
    verify_idempotency_checksum_match,
)
from apps.api.app.domains.ingestion.model_ingestion import (
    find_import_by_idempotency_or_checksum,
    get_import_by_id,
    insert_import_record,
    insert_prepared_input_record,
    query_samples_from_db,
    upload_import_file_to_storage,
)
from apps.api.app.domains.ingestion.schemas_ingestion import (
    PreparedInputCreate,
    SampleListResponse,
)


def raise_prepared_input_database_error(exc: Exception) -> NoReturn:
    error_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if str(error_code) == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un insumo registrado para esta clave de origen.",
        ) from exc
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la importación del archivo original.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo registrar el insumo preparado.",
    ) from exc


def check_idempotency_record(record: dict[str, Any], checksum: str) -> dict[str, Any]:
    if not verify_idempotency_checksum_match(record, checksum):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La clave de idempotencia ya fue usada con otro archivo.",
        )
    return record


def process_file_import_service(
    client,
    *,
    content: bytes,
    raw_filename: str | None,
    content_type: str | None,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], bool]:
    """Retorna (registro_importacion, fue_recuperado_por_idempotencia)."""
    checksum = compute_content_checksum(content)
    existing = find_import_by_idempotency_or_checksum(
        client, idempotency_key=idempotency_key, checksum=checksum
    )
    if existing:
        return check_idempotency_record(existing, checksum), True

    filename = sanitize_upload_filename(raw_filename)
    storage_path = checksum

    try:
        upload_import_file_to_storage(client, storage_path, content, content_type)
        created = insert_import_record(
            client,
            filename=filename,
            content_type=content_type,
            checksum=checksum,
            file_size=len(content),
            idempotency_key=idempotency_key,
            storage_path=storage_path,
        )
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            collision = find_import_by_idempotency_or_checksum(
                client, idempotency_key=idempotency_key, checksum=checksum
            )
            if collision:
                return check_idempotency_record(collision, checksum), True
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo completar el registro de la importación.",
        ) from exc

    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la importación.",
        )
    return created, False


def register_prepared_input_service(
    client, prepared_input: PreparedInputCreate
) -> dict[str, Any]:
    try:
        original = get_import_by_id(client, prepared_input.original_import_id)
    except Exception as exc:  # noqa: BLE001
        raise_prepared_input_database_error(exc)

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la importación del archivo original.",
        )

    try:
        created = insert_prepared_input_record(
            client,
            original_import_id=prepared_input.original_import_id,
            source_key=prepared_input.source_key,
            metadata=prepared_input.metadata,
        )
    except Exception as exc:  # noqa: BLE001
        raise_prepared_input_database_error(exc)

    if created:
        return created

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo registrar el insumo preparado.",
    )


def list_samples_service(
    client, *, quarantine: bool | None, page: int, page_size: int
) -> SampleListResponse:
    offset = (page - 1) * page_size
    limit = offset + page_size - 1
    items, total = query_samples_from_db(
        client, quarantine=quarantine, offset=offset, limit=limit
    )
    return SampleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
