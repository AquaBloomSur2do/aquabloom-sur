from typing import Annotated, Any, Literal
from uuid import UUID

from apps.scientific.app.core.database import supabase
from apps.scientific.app.core.dependencies import require_authenticated_user
from apps.scientific.app.domains.execution.model_execution import (
    get_dataset_version_for_training,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    EstimationConfig,
    JobCreate,
    JobResponse,
    TrainingConfig,
)
from apps.scientific.app.domains.execution.service_execution import (
    create_execution_job_service,
)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/executions", tags=["Gateway"])


class WebExecutionJobCreate(BaseModel):
    dataset_version_id: UUID | None = None
    job_type: Literal["TRAINING", "ESTIMATION", "training", "estimation"]
    config: dict[str, Any] = Field(default_factory=dict)


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


def _extract_user_id(user: dict[str, Any]) -> UUID:
    try:
        return UUID(str(user.get("sub")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario válido.",
        ) from exc


def _build_training_job_create(client, payload: WebExecutionJobCreate) -> JobCreate:
    raw_version_id = payload.dataset_version_id or payload.config.get("version_id")
    if raw_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Debe indicar una versión publicada del dataset para entrenar.",
        )

    try:
        version_id = UUID(str(raw_version_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El identificador de versión del dataset no es un UUID válido.",
        ) from exc

    raw_dataset_id = payload.config.get("dataset_id")
    if raw_dataset_id is None:
        version_record = get_dataset_version_for_training(client, version_id)
        if not version_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró la versión del dataset.",
            )
        raw_dataset_id = version_record.get("dataset_id")

    try:
        dataset_id = UUID(str(raw_dataset_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El identificador del dataset no es un UUID válido.",
        ) from exc

    training_kwargs: dict[str, Any] = {
        "dataset_id": dataset_id,
        "version_id": version_id,
    }
    if "epochs" in payload.config:
        training_kwargs["epochs"] = payload.config["epochs"]
    if "learning_rate" in payload.config:
        training_kwargs["learning_rate"] = payload.config["learning_rate"]

    try:
        training_config = TrainingConfig(**training_kwargs)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Configuración de entrenamiento inválida: {exc}",
        ) from exc

    return JobCreate(job_type="training", config=training_config)


def _build_estimation_job_create(payload: WebExecutionJobCreate) -> JobCreate:
    model_id = payload.config.get("model_id")
    scene_id = payload.config.get("scene_id")
    if not model_id or not scene_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La estimación requiere model_id y scene_id en config.",
        )

    try:
        model_version_id = UUID(str(model_id))
        normalized_scene_id = UUID(str(scene_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="model_id y scene_id deben ser UUID válidos.",
        ) from exc

    return JobCreate(
        job_type="estimation",
        config=EstimationConfig(
            model_id=model_version_id,
            scene_id=normalized_scene_id,
        ),
    )


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_web_execution_job(
    payload: WebExecutionJobCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    organization_id: Annotated[UUID, Header(alias="X-Organization-ID")],
    user: Annotated[dict[str, Any], Depends(require_authenticated_user)],
    x_idempotency_key: Annotated[
        str | None, Header(alias="X-Idempotency-Key", max_length=255)
    ] = None,
):
    client = _require_database()
    user_id = _extract_user_id(user)

    idempotency_key = x_idempotency_key.strip() if x_idempotency_key else None
    if idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    normalized_type = payload.job_type.lower()
    if normalized_type == "training":
        job_create = _build_training_job_create(client, payload)
    else:
        job_create = _build_estimation_job_create(payload)

    return create_execution_job_service(
        client,
        payload=job_create,
        background_tasks=background_tasks,
        idempotency_key=idempotency_key,
        user_id=user_id,
        organization_id=organization_id,
        correlation_id=request.state.correlation_id,
    )
