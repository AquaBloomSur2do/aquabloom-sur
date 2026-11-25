import csv
import hashlib
import io
import math
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from apps.scientific.app.core.config import settings

MAX_TRAINING_FILE_SIZE = 1024 * 1024  # Límite por contrato: 1 MiB


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
    bearer_token: str | None = None,
    base_url: str | None = None,
    client: httpx.Client | None = None,
    *,
    internal_service_token: str | None = None,
    organization_id: UUID | str | None = None,
    user_id: UUID | str | None = None,
) -> ConsumedDataset:
    """
    Consume una versión publicada del dataset por contrato HTTP:
    1. Obtiene el manifiesto desde Core API.
    2. Descarga el archivo CSV mediante el proxy seguro.
    3. Verifica que el checksum SHA-256 y las columnas coincidan con el manifiesto.
    """
    api_base = (base_url or settings.core_api_url).rstrip("/")
    if internal_service_token:
        if organization_id is None or user_id is None:
            raise ValueError(
                "organization_id y user_id son requeridos para la descarga interna."
            )
        headers = {"X-Internal-Token": internal_service_token}
        request_params = {
            "organization_id": str(organization_id),
            "user_id": str(user_id),
        }
        meta_path = f"/internal/v1/datasets/versions/{version_id}/training-file"
    elif bearer_token:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        request_params = None
        meta_path = f"/api/v1/datasets/versions/{version_id}/training-file"
    else:
        raise ValueError("Se requiere una credencial para consumir el contrato Core.")

    should_close = client is None
    http_client = client or httpx.Client(base_url=api_base, timeout=15.0)

    try:
        meta_resp = http_client.get(
            meta_path,
            headers=headers,
            params=request_params,
        )

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

        if not reader.fieldnames or reader.fieldnames != manifest.variables:
            raise DatasetContractError(
                f"Las columnas del CSV ({reader.fieldnames}) no coinciden con las variables del manifiesto ({manifest.variables}).",
                status_code=422,
            )

        parsed_rows: list[dict[str, float]] = []
        for row in reader:
            parsed_row: dict[str, float] = {}
            for column in manifest.variables:
                raw_value = row.get(column)
                if raw_value is None or not raw_value.strip():
                    raise DatasetContractError(
                        f"Valor faltante en la columna '{column}' del dataset de entrenamiento.",
                        status_code=422,
                    )

                try:
                    value = float(raw_value)
                except ValueError as exc:
                    raise DatasetContractError(
                        f"Valor no numérico en la columna '{column}' del dataset de entrenamiento: {raw_value}",
                        status_code=422,
                    ) from exc

                if not math.isfinite(value):
                    raise DatasetContractError(
                        f"Valor no finito en la columna '{column}' del dataset de entrenamiento.",
                        status_code=422,
                    )

                parsed_row[column] = value
            parsed_rows.append(parsed_row)

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
    except httpx.RequestError as exc:
        raise DatasetContractError(
            "No se pudo contactar el contrato de datasets de Core.",
            status_code=502,
        ) from exc
    finally:
        if should_close:
            http_client.close()
