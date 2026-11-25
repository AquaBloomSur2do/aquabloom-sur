import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.main import app

HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)

client = TestClient(app)


def normalize_path(path: str) -> str:
    """Normaliza una ruta para comparar operaciones equivalentes.

    - Garantiza una barra inicial.
    - Colapsa barras repetidas.
    - Elimina la barra final salvo en la raíz.
    - Unifica los nombres de los parámetros de ruta: ``/{id}`` y ``/{lake_id}``
      se consideran la misma ruta.
    """
    normalized = (path or "/").strip() or "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    normalized = re.sub(r"/+", "/", normalized)
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    normalized = re.sub(r"\{[^{}]*\}", "{}", normalized)
    return normalized or "/"


def find_duplicate_openapi_operations(
    schema: dict[str, Any],
) -> dict[tuple[str, str], list[str]]:
    """Devuelve las operaciones OpenAPI duplicadas por ``(método, ruta)``."""
    operations: dict[tuple[str, str], list[str]] = defaultdict(list)

    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            operation_id = (
                operation.get("operationId")
                if isinstance(operation, dict)
                else None
            )
            key = (method.upper(), normalize_path(path))
            operations[key].append(
                operation_id or f"{method.upper()} {path}"
            )

    return {key: ids for key, ids in operations.items() if len(ids) > 1}


def _iter_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """Recorre rutas incluyendo routers anidados por ``include_router``."""
    for route in routes:
        nested_router = getattr(route, "original_router", None)
        nested_routes = (
            getattr(nested_router, "routes", None)
            if nested_router is not None
            else getattr(route, "routes", None)
        )
        if nested_routes:
            yield from _iter_routes(nested_routes)
        else:
            yield route


def find_duplicate_routes(
    routes: Iterable[Any],
) -> dict[tuple[str, str], list[str]]:
    """Devuelve rutas duplicadas por ``(método, ruta normalizada)``.

    Inspecciona la tabla de enrutamiento real, incluyendo rutas registradas
    con ``include_in_schema=False`` como los proxies del Gateway.
    """
    operations: dict[tuple[str, str], list[str]] = defaultdict(list)

    for route in _iter_routes(routes):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        name = getattr(route, "name", None) or f"{path}"
        for method in methods:
            if method.lower() not in HTTP_METHODS:
                continue
            operations[(method.upper(), normalize_path(path))].append(name)

    return {key: names for key, names in operations.items() if len(names) > 1}


def test_gateway_openapi_has_no_duplicate_method_and_path_operations():
    schema = app.openapi()

    assert schema["paths"], "El OpenAPI del Gateway no expone rutas"
    assert find_duplicate_openapi_operations(schema) == {}


def test_gateway_openapi_endpoint_has_no_duplicate_method_and_path_operations():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert find_duplicate_openapi_operations(response.json()) == {}


def test_gateway_route_table_has_no_duplicate_method_and_path_routes():
    collisions = find_duplicate_routes(app.routes)

    assert collisions == {}, f"Colisiones de rutas detectadas: {collisions}"


def test_openapi_detector_flags_duplicate_method_and_path():
    schema = {
        "paths": {
            "/api/v1/lagos/{lake_id}": {
                "get": {"operationId": "obtener_lago"},
            },
            "/api/v1/lagos/{id}/": {
                "get": {"operationId": "obtener_lago_duplicado"},
            },
        }
    }

    collisions = find_duplicate_openapi_operations(schema)

    assert ("GET", "/api/v1/lagos/{}") in collisions
    assert collisions[("GET", "/api/v1/lagos/{}")] == [
        "obtener_lago",
        "obtener_lago_duplicado",
    ]


def test_openapi_detector_ignores_same_path_with_different_methods():
    schema = {
        "paths": {
            "/api/v1/lagos": {
                "get": {"operationId": "listar_lagos"},
                "post": {"operationId": "crear_lago"},
            }
        }
    }

    assert find_duplicate_openapi_operations(schema) == {}


def test_openapi_detector_ignores_non_method_keys():
    schema = {
        "paths": {
            "/api/v1/lagos": {
                "get": {"operationId": "listar_lagos"},
                "parameters": [],
                "summary": "Catálogo de lagos",
            }
        }
    }

    assert find_duplicate_openapi_operations(schema) == {}


def test_route_table_detector_flags_duplicate_method_and_path():
    collision_app = FastAPI()
    collision_app.add_api_route(
        "/api/v1/colision",
        lambda: None,
        methods=["GET"],
        name="primera_ruta",
    )
    collision_app.add_api_route(
        "/api/v1/colision/",
        lambda: None,
        methods=["GET"],
        name="segunda_ruta",
    )

    collisions = find_duplicate_routes(collision_app.routes)

    assert ("GET", "/api/v1/colision") in collisions
    assert collisions[("GET", "/api/v1/colision")] == [
        "primera_ruta",
        "segunda_ruta",
    ]


def test_route_table_detector_ignores_same_path_with_different_methods():
    collision_app = FastAPI()
    collision_app.add_api_route(
        "/api/v1/colision",
        lambda: None,
        methods=["GET"],
        name="obtener",
    )
    collision_app.add_api_route(
        "/api/v1/colision",
        lambda: None,
        methods=["POST"],
        name="crear",
    )

    assert find_duplicate_routes(collision_app.routes) == {}
