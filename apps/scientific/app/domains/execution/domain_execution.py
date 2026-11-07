import asyncio
from typing import Any
from uuid import UUID

from apps.scientific.app.domains.execution.schemas_execution import JobCreate

JOB_TIMEOUT_SECONDS = 10.0


def job_matches_request(
    job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return job.get("job_type") == payload.job_type and job.get("config") == config


def build_job_accepted_response(job: dict[str, Any]) -> dict[str, Any]:
    job_id = UUID(str(job["id"]))
    return {
        "job_id": job_id,
        "status": job["status"],
        "status_url": f"/api/v1/executions/{job_id}",
    }


async def run_scientific_algorithm(config: dict[str, Any]) -> dict[str, Any]:
    scene_id = config.get("scene_id", "")
    if scene_id == "scene_fail":
        raise RuntimeError(
            "Excepción interna: Fallo al procesar los tensores de la escena."
        )
    if scene_id == "scene_timeout":
        await asyncio.sleep(2.0)
    else:
        await asyncio.sleep(0.1)
    return {"accuracy": 0.98, "processed_pixels": 102400}

