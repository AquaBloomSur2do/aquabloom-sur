import hashlib


def compute_content_checksum(content: bytes) -> str:
    """Calcula el hash SHA-256 del contenido binario del archivo importado."""
    return hashlib.sha256(content).hexdigest()


def sanitize_upload_filename(raw_filename: str | None) -> str:
    """Normaliza el nombre del archivo eliminando rutas de sistema operativo."""
    filename = (raw_filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    return filename if filename else "upload"


def verify_idempotency_checksum_match(record: dict, checksum: str) -> bool:
    """Comprueba que un registro recuperado por idempotency_key corresponda al mismo archivo."""
    return record.get("checksum") == checksum
