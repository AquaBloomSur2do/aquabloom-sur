from typing import Any
from uuid import UUID

from supabase import Client


def find_import_by_idempotency_or_checksum(
    client: Client, *, idempotency_key: str | None, checksum: str
) -> dict[str, Any] | None:
    if idempotency_key:
        response = (
            client.table("imports")
            .select("*")
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]

    response = (
        client.table("imports")
        .select("*")
        .eq("checksum", checksum)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def upload_import_file_to_storage(
    client: Client, storage_path: str, content: bytes, content_type: str | None
) -> None:
    client.storage.from_("imports").upload(
        storage_path,
        content,
        file_options={
            "content-type": content_type or "application/octet-stream",
            "upsert": "true",
        },
    )


def insert_import_record(
    client: Client,
    *,
    filename: str,
    content_type: str | None,
    checksum: str,
    file_size: int,
    idempotency_key: str | None,
    storage_path: str,
) -> dict[str, Any] | None:
    database_response = (
        client.table("imports")
        .insert(
            {
                "filename": filename,
                "content_type": content_type,
                "checksum": checksum,
                "file_size": file_size,
                "idempotency_key": idempotency_key,
                "storage_path": storage_path,
                "status": "pending",
            }
        )
        .execute()
    )
    return database_response.data[0] if database_response.data else None


def get_import_by_id(client: Client, import_id: UUID | str) -> dict[str, Any] | None:
    original = (
        client.table("imports")
        .select("id")
        .eq("id", str(import_id))
        .limit(1)
        .execute()
    )
    data = getattr(original, "data", None) if original else None
    return data[0] if data else None


def insert_prepared_input_record(
    client: Client,
    *,
    original_import_id: UUID | str,
    source_key: str,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    response = (
        client.table("prepared_inputs")
        .insert(
            {
                "original_import_id": str(original_import_id),
                "source_key": source_key,
                "metadata": metadata,
            }
        )
        .execute()
    )
    response_data = getattr(response, "data", None) if response else None
    return response_data[0] if response_data and len(response_data) > 0 else None


def query_samples_from_db(
    client: Client,
    *,
    quarantine: bool | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    query = client.table("samples").select("*", count="exact")
    if quarantine is not None:
        query = query.eq("is_quarantined", quarantine)
    query = query.range(offset, limit)
    response = query.execute()
    return (
        response.data or [],
        response.count if response.count is not None else 0,
    )
