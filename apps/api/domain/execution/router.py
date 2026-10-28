import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

# Diccionario temporal en memoria para respaldar las pruebas locales de este ticket
JOBS_DB: dict[str, dict[str, Any]] = {}


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def create_execution_job(payload: dict[str, Any]):
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "job_type": payload.get("job_type"),
        "config": payload.get("config"),
        "status": "pending",
    }
    JOBS_DB[job_id] = job_data
    
    return {
        "job_id": job_id,
        "status": "pending",
        "status_url": f"/api/v1/executions/{job_id}",
        "message": "Job accepted and processing in background",
    }


@router.get("/{job_id}", status_code=status.HTTP_200_OK)
def get_job_status(job_id: str):
    if job_id not in JOBS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )
        
    return JOBS_DB[job_id]
