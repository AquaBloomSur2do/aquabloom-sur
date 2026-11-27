from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status

from apps.api.app.core.dependencies import require_permission
from apps.api.app.domains.library.domain_library import (
    LIBRARY_READ_PERMISSION,
    LIBRARY_ROUTE_PREFIX,
)
from apps.api.app.domains.library.schemas_library import LibraryStartupStatus
from apps.api.app.domains.library.service_library import (
    collect_application_route_paths,
    ensure_library_module_enabled,
    get_library_startup_status,
)

router = APIRouter(
    prefix=LIBRARY_ROUTE_PREFIX,
    tags=["Library"],
    dependencies=[Depends(ensure_library_module_enabled)],
)


@router.get(
    "/health",
    response_model=LibraryStartupStatus,
    status_code=status.HTTP_200_OK,
    summary="Verificar arranque y autorización del módulo de biblioteca en Core",
)
def library_module_health(
    request: Request,
    user: Annotated[
        dict[str, Any], Depends(require_permission(LIBRARY_READ_PERMISSION))
    ],
) -> LibraryStartupStatus:
    route_paths = collect_application_route_paths(request.app)
    return get_library_startup_status(user, registered_paths=route_paths)


