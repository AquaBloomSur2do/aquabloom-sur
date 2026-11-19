import csv
import hashlib
import io
import math
from typing import Any

from fastapi import HTTPException, status
from storage3.utils import StorageException

from apps.scientific.app.core.database import supabase


def fetch_training_data(dataset_id: str, version_id: str) -> list[dict[str, Any]]:
    """Descarga y lee el archivo CSV validando manifiesto, checksum y datos."""
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexión a la base de datos",
        )

    response = (
        supabase.schema("dataset")
        .table("training_manifests")
        .select("storage_path, checksum")
        .eq("version_id", version_id)
        .limit(1)
        .execute()
    )
    manifests = response.data or []
    if not manifests:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manifiesto de la versión no encontrado",
        )

    manifest = manifests[0]
    storage_path = manifest.get("storage_path")
    expected_checksum = manifest.get("checksum")
    if (
        not isinstance(storage_path, str)
        or not storage_path
        or not isinstance(expected_checksum, str)
        or len(expected_checksum) != 64
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El manifiesto del archivo de entrenamiento no es válido",
        )

    try:
        file_response = supabase.storage.from_("training_files").download(storage_path)
    except StorageException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo de entrenamiento no encontrado",
        ) from exc

    actual_checksum = hashlib.sha256(file_response).hexdigest()
    if actual_checksum != expected_checksum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Checksum del archivo de entrenamiento incorrecto",
        )

    try:
        csv_text = file_response.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El archivo de entrenamiento no está codificado en UTF-8",
        ) from exc
    reader = csv.DictReader(io.StringIO(csv_text))

    if not reader.fieldnames or "clorofila_a" not in reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El archivo CSV no contiene la columna objetivo 'clorofila_a'",
        )

    data = list(reader)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El archivo CSV está vacío",
        )

    validated_data = []
    for row in data:
        val_str = row.get("clorofila_a")
        if val_str is None or val_str.strip() == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Valor faltante en la columna 'clorofila_a'",
            )
        try:
            val_float = float(val_str)
            if math.isnan(val_float) or math.isinf(val_float):
                raise ValueError()
            row["clorofila_a"] = val_float
            validated_data.append(row)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Valor no numérico o inválido en 'clorofila_a': {val_str}",
            ) from exc

    return validated_data


def split_training_validation(
    data: list[dict[str, Any]], split_ratio: float = 0.8
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Garantiza observaciones para entrenamiento y evaluación."""
    if len(data) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Se requieren al menos 2 observaciones para evaluar el modelo.",
        )

    train_size = max(1, int(len(data) * split_ratio))
    if train_size == len(data):
        train_size = len(data) - 1

    train_data = data[:train_size]
    val_data = data[train_size:]

    return train_data, val_data
