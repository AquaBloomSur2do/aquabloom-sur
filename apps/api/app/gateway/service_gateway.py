from uuid import uuid4

import httpx
from fastapi import Request, Response

PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
RESPONSE_HEADERS_TO_DROP = HOP_BY_HOP_HEADERS | {"content-encoding"}


async def forward_proxy_request(
    request: Request,
    service_url: str,
    path: str = "",
) -> Response:
    correlation_id = (
        request.headers.get("x-correlation-id")
        or request.headers.get("correlation_id")
        or str(uuid4())
    )
    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }
    headers["X-Correlation-ID"] = correlation_id

    target_url = f"{service_url.rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    async with httpx.AsyncClient() as client:
        upstream_response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=await request.body(),
        )

    response_headers = {
        name: value
        for name, value in upstream_response.headers.items()
        if name.lower() not in RESPONSE_HEADERS_TO_DROP
    }
    response_headers["X-Correlation-ID"] = correlation_id
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
