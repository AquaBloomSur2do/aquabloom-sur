import logging
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException, status

from apps.api.app.core.config import settings
from apps.api.app.domains.library.domain_library import (
    LIBRARY_AUTH_PROVIDER,
    LIBRARY_HEALTH_ROUTE,
    LIBRARY_MODULE_NAME,
    LIBRARY_READ_PERMISSION,
    LIBRARY_ROUTE_PREFIX,
    extract_authenticated_subject,
    is_library_route_registered,
)
from apps.api.app.domains.library.schemas_library import (
    LibraryAuthorizationInfo,
    LibraryStartupStatus,
)

logger = logging.getLogger(__name__)


def collect_application_route_paths(
    container: Any,
    *,
    prefix: str = "",
) -> list[str]:
    """Recopila rutas registradas soportando rutas planas y _IncludedRouter."""
    collected: list[str] = []
    for route in getattr(container, "routes", []):
        path = getattr(route, "path", None)
        if isinstance(path, str):
            collected.append(f"{prefix}{path}")
            continue

        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            include_context = getattr(route, "include_context", None)
            nested_prefix = getattr(include_context, "prefix", "") or ""
            collected.extend(
                collect_application_route_paths(
                    original_router,
                    prefix=f"{prefix}{nested_prefix}",
                )
            )
            continue

        if hasattr(route, "routes"):
            collected.extend(
                collect_application_route_paths(route, prefix=prefix)
            )
    return collected


def ensure_library_module_enabled() -> None:
    """Rechaza el acceso cuando el módulo de biblioteca está deshabilitado."""
    if not settings.library_module_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El módulo de biblioteca no está habilitado.",
        )


def get_library_startup_status(
    user_payload: dict[str, Any] | None = None,
    *,
    registered_paths: Iterable[str] | None = None,
) -> LibraryStartupStatus:
    """Construye el reporte de estado y autorización del módulo de biblioteca."""
    enabled = bool(settings.library_module_enabled)
    routes = (
        sorted(
            {
                path
                for path in registered_paths
                if isinstance(path, str) and path.startswith(LIBRARY_ROUTE_PREFIX)
            }
        )
        if registered_paths is not None
        else [LIBRARY_HEALTH_ROUTE]
    )
    return LibraryStartupStatus(
        module=LIBRARY_MODULE_NAME,
        status="ready" if enabled else "disabled",
        enabled=enabled,
        environment=settings.environment,
        authorization=LibraryAuthorizationInfo(
            provider=LIBRARY_AUTH_PROVIDER,
            required_permission=LIBRARY_READ_PERMISSION,
            authenticated_subject=extract_authenticated_subject(user_payload),
        ),
        routes=routes,
    )


def verify_library_module_startup(application: Any) -> LibraryStartupStatus:
    """Verifica en arranque que el módulo quedó registrado en Core."""
    route_paths = collect_application_route_paths(application)
    if not is_library_route_registered(route_paths):
        raise RuntimeError(
            f"El módulo '{LIBRARY_MODULE_NAME}' no registró la ruta "
            f"'{LIBRARY_HEALTH_ROUTE}'."
        )

    startup_status = get_library_startup_status(registered_paths=route_paths)
    logger.info(
        "Arranque del módulo de biblioteca verificado | enabled=%s | status=%s | env=%s",
        startup_status.enabled,
        startup_status.status,
        startup_status.environment,
    )
    return startup_status

