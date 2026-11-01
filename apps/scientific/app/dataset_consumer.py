import csv
import hashlib
import io
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings

MAX_TRAINING_FILE_SIZE = 1024 * 1024  # 1 MiB


class DatasetContractError(Exception):
    """Excepción base cuando el dataset incumple el contrato o falla su validación."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TrainingManifestContract(BaseModel):
    version_id: UUID
    manifest_id: UUID
    variables: list[str] = Field(min_length=1)
    checksum: str = Field(min_length=64, max_length=64)
    download_url: str

    model_config = ConfigDict(from_attributes=True)


class ConsumedDataset(BaseModel):
    manifest: TrainingManifestContract
    rows: list[dict[str, float]]
    raw_bytes: bytes

    model_config = ConfigDict(arbitrary_types_allowed=True)


def fetch_and_verify_training_dataset(
    version_id: UUID | str,
    bearer_token: str,
    base_url: str | None = None,
    client: httpx.Client | None = None,
) -> ConsumedDataset:
    """
    Consume una versión publicada del dataset por contrato HTTP:
    1. Obtiene el manifiesto desde Core API.
    2. Descarga el archivo CSV mediante el proxy seguro.
    3. Verifica que el checksum SHA-256 y las columnas coincidan con el manifiesto.
    """
    api_base = (base_url or settings.core_api_url).rstrip("/")
    headers = {"Authorization": f"Bearer {bearer_token}"}

    should_close = client is None
    http_client = client or httpx.Client(base_url=api_base, timeout=15.0)

    try:
        meta_path = f"/api/v1/datasets/versions/{version_id}/training-file"
        meta_resp = http_client.get(meta_path, headers=headers)

        if meta_resp.status_code != 200:
            raise DatasetContractError(
                f"No se pudo obtener el manifiesto del dataset (HTTP {meta_resp.status_code}).",
                status_code=meta_resp.status_code,
            )

        manifest = TrainingManifestContract.model_validate(meta_resp.json())

        download_path = manifest.download_url
        if not download_path.startswith("http"):
            download_path = f"/{download_path.lstrip('/')}"

        file_resp = http_client.get(download_path, headers=headers)
        if file_resp.status_code != 200:
            raise DatasetContractError(
                f"Fallo al descargar el archivo de entrenamiento (HTTP {file_resp.status_code}).",
                status_code=file_resp.status_code,
            )

        file_bytes = file_resp.content

        if len(file_bytes) > MAX_TRAINING_FILE_SIZE:
            raise DatasetContractError(
                "El archivo descargado excede el tamaño máximo permitido por contrato (1 MiB).",
                status_code=502,
            )

        calculated_checksum = hashlib.sha256(file_bytes).hexdigest()
        if calculated_checksum != manifest.checksum.lower():
            raise DatasetContractError(
                "Violación de integridad: el checksum SHA-256 del archivo no coincide con el manifiesto.",
                status_code=502,
            )

        csv_text = file_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(csv_text))

        if reader.fieldnames != manifest.variables:
            raise DatasetContractError(
                f"Las columnas del CSV ({reader.fieldnames}) no coinciden con las variables del manifiesto ({manifest.variables}).",
                status_code=422,
            )

        parsed_rows: list[dict[str, float]] = []
        for row in reader:
            try:
                parsed_rows.append({col: float(row[col]) for col in manifest.variables})
            except (ValueError, TypeError, KeyError) as exc:
                raise DatasetContractError(
                    f"Fila con valores numéricos inválidos en el dataset de entrenamiento: {exc}",
                    status_code=422,
                ) from exc

        if not parsed_rows:
            raise DatasetContractError(
                "El archivo de entrenamiento está vacío (sin filas de datos).",
                status_code=422,
            )

        return ConsumedDataset(
            manifest=manifest,
            rows=parsed_rows,
            raw_bytes=file_bytes,
        )
    finally:
        if should_close:
            http_client.close()
