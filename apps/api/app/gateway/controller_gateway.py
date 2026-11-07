from fastapi import APIRouter, Request, Response

from apps.api.app.core.config import settings
from apps.api.app.gateway.service_gateway import (
    PROXY_METHODS,
    forward_proxy_request,
)

router = APIRouter(tags=["Gateway"])

# Alias para mantener compatibilidad con tests unitarios que importen _proxy_request
_proxy_request = forward_proxy_request


async def proxy_satellite(request: Request, path: str = "") -> Response:
    return await forward_proxy_request(
        request, settings.satellite_service_url, path
    )


async def proxy_scientific(request: Request, path: str = "") -> Response:
    return await forward_proxy_request(
        request, settings.scientific_service_url, path
    )


router.add_api_route(
    "/api/v1/satellite",
    proxy_satellite,
    methods=PROXY_METHODS,
    name="proxy_satellite_root",
    include_in_schema=False,
)
router.add_api_route(
    "/api/v1/satellite/{path:path}",
    proxy_satellite,
    methods=PROXY_METHODS,
    name="proxy_satellite_path",
    include_in_schema=False,
)
router.add_api_route(
    "/api/v1/scientific",
    proxy_scientific,
    methods=PROXY_METHODS,
    name="proxy_scientific_root",
    include_in_schema=False,
)
router.add_api_route(
    "/api/v1/scientific/{path:path}",
    proxy_scientific,
    methods=PROXY_METHODS,
    name="proxy_scientific_path",
    include_in_schema=False,
)
