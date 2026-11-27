from typing import Any

from apps.api.app.domains.library.domain_library import LIBRARY_STORAGE_BUCKET


def upload_library_file_to_storage(
    client: Any,
    storage_path: str,
    content: bytes,
    content_type: str = "text/csv",
    bucket: str = LIBRARY_STORAGE_BUCKET,
) -> str:
    """Guarda los bytes del archivo de biblioteca en el bucket de Storage."""
    client.storage.from_(bucket).upload(
        storage_path,
        content,
        file_options={
            "content-type": content_type or "application/octet-stream",
            "upsert": "true",
        },
    )
    return storage_path


def download_library_file_from_storage(
    client: Any,
    storage_path: str,
    bucket: str = LIBRARY_STORAGE_BUCKET,
) -> bytes:
    """Descarga los bytes del archivo de biblioteca desde Storage."""
    downloaded = client.storage.from_(bucket).download(storage_path)
    if not isinstance(downloaded, bytes):
        raise TypeError("El archivo descargado desde Storage no contiene bytes.")
    return downloaded
