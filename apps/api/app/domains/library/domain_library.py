import hashlib
from pathlib import PurePosixPath
from uuid import UUID

LIBRARY_STORAGE_BUCKET = "library_files"
SHA256_HEX_LENGTH = 64
HEX_CHARS = frozenset("0123456789abcdef")


def compute_library_file_checksum(content: bytes) -> str:

    if not isinstance(content, bytes) or len(content) == 0:
        raise ValueError("El contenido del archivo de biblioteca no puede estar vacío.")
    return hashlib.sha256(content).hexdigest()


def validate_library_checksum(checksum: str) -> str:
    
    if not isinstance(checksum, str):
        raise TypeError("El checksum SHA-256 debe ser una cadena de texto.")
    normalized = checksum.strip().lower()
    if len(normalized) != SHA256_HEX_LENGTH or any(
        char not in HEX_CHARS for char in normalized
    ):
        raise ValueError("El checksum SHA-256 debe tener 64 caracteres hexadecimales.")
    return normalized


def build_library_storage_path(
    resource_id: UUID | str,
    version_id: UUID | str,
    filename: str,
) -> str:
    
    normalized_resource = str(UUID(str(resource_id)))
    normalized_version = str(UUID(str(version_id)))
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("El nombre de archivo de biblioteca es obligatorio.")
    raw_name = filename.strip()
    if "/" in raw_name or "\\" in raw_name or raw_name in {".", ".."}:
        raise ValueError("El nombre de archivo contiene segmentos de ruta no válidos.")
    clean_name = PurePosixPath(raw_name).name
    if not clean_name or clean_name in {".", ".."}:
        raise ValueError("El nombre de archivo de biblioteca no es válido.")
    return f"{normalized_resource}/{normalized_version}/{clean_name}"


def verify_library_file_integrity(content: bytes, expected_checksum: str) -> bool:

    normalized_expected = validate_library_checksum(expected_checksum)
    actual_checksum = compute_library_file_checksum(content)
    return actual_checksum == normalized_expected
