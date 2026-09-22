# 1. Definición inmutable de acciones del catálogo
CATALOG_ACTIONS = {
    "READ": "catalog:read",
    "CREATE": "catalog:create",
    "UPDATE": "catalog:update",
    "DISABLE": "catalog:disable",
}

# 2. Matriz de Control de Acceso (RBAC) para los 4 roles requeridos
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "administrador": [
        CATALOG_ACTIONS["READ"],
        CATALOG_ACTIONS["CREATE"],
        CATALOG_ACTIONS["UPDATE"],
        CATALOG_ACTIONS["DISABLE"],
    ],
    "supervisor": [
        CATALOG_ACTIONS["READ"],
        CATALOG_ACTIONS["UPDATE"],
    ],
    "investigador": [
        CATALOG_ACTIONS["READ"],
        CATALOG_ACTIONS["CREATE"],
    ],
    "auditor": [
        CATALOG_ACTIONS["READ"],
    ],
}


def check_catalog_permission(role: str, action: str) -> bool:
    """
    Evalúa si un rol posee los privilegios para una acción de catálogo.
    Lanza un ValueError si se inyecta una acción no registrada en el sistema.
    """
    # Validación estricta exigida por el Criterio de Aceptación
    if action not in CATALOG_ACTIONS.values():
        raise ValueError(f"Acción de seguridad desconocida o no válida: {action}")

    # Evaluación de permisos (por defecto vacío si el rol no existe)
    allowed_actions = ROLE_PERMISSIONS.get(role, [])
    return action in allowed_actions
