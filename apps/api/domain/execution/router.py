import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

# Modelos y esquemas de ejemplo (ajusta según tus imports si ya los tienes separados)
# ...

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def create_execution_job(payload: dict[str, Any]):
    # Tu lógica de creación e inserción en Supabase (tabla scientific_jobs)
    job_id = str(uuid.uuid4())
    return {
        "job_id": job_id,
        "status": "pending",
        "status_url": f"/api/v1/executions/{job_id}",
        "message": "Job accepted and processing in background"
    }


@router.get("/{job_id}", status_code=status.HTTP_200_OK)
def get_job_status(job_id: str):
    # Tu lógica de consulta a Supabase
    # Si no se encuentra, asegúrate de lanzar el 404 con este mensaje exacto:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No se encontró el trabajo."
    )
