from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)

from apps.scientific.app.core.database import supabase
from apps.scientific.app.core.dependencies import (
    require_authenticated_user,
    require_internal_service,
)
from apps.scientific.app.domains.execution.domain_execution import (
    JOB_TIMEOUT_SECONDS,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    JobCreate,
    JobResponse,
    JobStatus,
    ModelArtifactAccess,
)
from apps.scientific.app.domains.execution.service_execution import (
    create_execution_job_service,
    get_job_status_service,
    get_model_artifact_access_service,
    process_scientific_job,
)

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])

JOB_ACCESS_ERROR_RESPONSES = {
    401: {"description": "No autenticado o token inválido."},
    404: {"description": "Trabajo no encontrado o sin acceso en la organización."},
    503: {"description": "Servicio de base de datos no disponible."},
}

# Alias de compatibilidad para tests que parchean _process_scientific_job o JOB_TIMEOUT_SECONDS
_process_scientific_job = process_scientific_job

__all__ = ["JOB_TIMEOUT_SECONDS", "_process_scientific_job", "router"]


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    status_code=status.HTTP_200_OK,
    summary="Consultar estado y resultado de un trabajo científico",
    responses=JOB_ACCESS_ERROR_RESPONSES,
)
def get_job_status(
    job_id: UUID,
    organization_id: UUID = Header(alias="X-Organization-ID"),  # noqa: B008
    user: dict = Depends(require_authenticated_user),  # noqa: B008
):
    client = _require_database()
    try:
        user_id = UUID(str(user.get("sub")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario válido.",
        ) from exc
    return get_job_status_service(client, job_id, user_id, organization_id)


@router.get(
    "/{job_id}/artifact",
    response_model=ModelArtifactAccess,
    status_code=status.HTTP_200_OK,
    summary="Solicitar acceso temporal al artefacto de un trabajo científico",
    responses=JOB_ACCESS_ERROR_RESPONSES,
)
def get_job_artifact_access(
    job_id: UUID,
    response: Response,
    organization_id: UUID = Header(alias="X-Organization-ID"),  # noqa: B008
    user: dict = Depends(require_authenticated_user),  # noqa: B008
):
    client = _require_database()
    try:
        user_id = UUID(str(user.get("sub")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario válido.",
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return get_model_artifact_access_service(client, job_id, user_id, organization_id)


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    organization_id: UUID = Header(alias="X-Organization-ID"),  # noqa: B008
    user: dict = Depends(require_authenticated_user),  # noqa: B008
    x_idempotency_key: str | None = Header(
        default=None, alias="X-Idempotency-Key", max_length=255
    ),
):
    client = _require_database()
    try:
        user_id = UUID(str(user.get("sub")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario válido.",
        ) from exc

    idempotency_key = x_idempotency_key.strip() if x_idempotency_key else None

    if idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    return create_execution_job_service(
        client,
        payload=payload,
        background_tasks=background_tasks,
        idempotency_key=idempotency_key,
        user_id=user_id,
        organization_id=organization_id,
        correlation_id=request.state.correlation_id,
    )
