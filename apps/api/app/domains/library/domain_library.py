from apps.api.app.core.permissions import CATALOG_ACTIONS

LIBRARY_MODULE_NAME = "library"
LIBRARY_ROUTE_PREFIX = "/api/v1/library"
LIBRARY_HEALTH_ROUTE = f"{LIBRARY_ROUTE_PREFIX}/health"
LIBRARY_READ_PERMISSION = CATALOG_ACTIONS["READ"]
LIBRARY_AUTH_PROVIDER = "core_supabase_jwt_rbac"


def extract_authenticated_subject(user_payload: dict | None) -> str | None:
    """Extrae el identificador del sujeto autenticado desde el JWT de Core."""
    if not isinstance(user_payload, dict):
        return None
    for key in ("sub", "id"):
        value = user_payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def is_library_route_registered(route_paths: list[str]) -> bool:
    """Comprueba que la ruta verificable del módulo de biblioteca esté montada."""
    return LIBRARY_HEALTH_ROUTE in route_paths


