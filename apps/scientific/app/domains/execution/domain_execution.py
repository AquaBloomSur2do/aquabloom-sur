import asyncio
from typing import Any

from apps.scientific.app.domains.execution.baseline_execution import calculate_baseline
from apps.scientific.app.domains.execution.data_execution import (
    fetch_training_data,
    split_training_validation,
)
from apps.scientific.app.domains.execution.schemas_execution import JobCreate

JOB_TIMEOUT_SECONDS = 300


def build_job_accepted_response(job: dict[str, Any]) -> dict[str, Any]:
    job_id = job.get("id") or job.get("job_id")
    return {
        "job_id": str(job_id),
        "status": job.get("status", "queued"),
        "message": "Trabajo encolado y en procesamiento.",
        "status_url": f"/api/v1/executions/{job_id}",
    }

def job_matches_request(
    existing_job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return (
        existing_job.get("job_type") == payload.job_type
        and existing_job.get("config") == config
    )


async def run_scientific_algorithm(
    job_type: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Ejecuta el algoritmo científico real (baseline para S2-155)."""
    await asyncio.sleep(1)

    if job_type != "training":
        return {"message": f"Tipo de trabajo '{job_type}' no implementado aún."}

    dataset_id = config.get("dataset_id")
    version_id = config.get("version_id")

    if not dataset_id or not version_id:
        raise ValueError("Faltan dataset_id o version_id en la configuración.")

    # 1. Cargar datos de entrenamiento desde el storage
    raw_data = fetch_training_data(str(dataset_id), str(version_id))
    
    # 2. Separar particiones (80% entrenamiento, 20% validación)
    train_data, val_data = split_training_validation(raw_data, split_ratio=0.8)
    
    # 3. Calcular baseline exclusivo sobre entrenamiento y validar
    result = calculate_baseline(train_data, val_data)

    return result
