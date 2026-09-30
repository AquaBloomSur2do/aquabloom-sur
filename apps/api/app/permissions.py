# 1. Definición inmutable de acciones del catálogo
CATALOG_ACTIONS = {
    "READ": "catalog:read",
    "CREATE": "catalog:create",
    "UPDATE": "catalog:update",
    "DISABLE": "catalog:disable",
}

CATALOG_DISABLE = CATALOG_ACTIONS["DISABLE"]

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


def has_permission(user_data: dict | None, required_permission: str) -> bool:
    """Resuelve permisos explícitos o los concedidos por un rol conocido."""
    if not isinstance(user_data, dict):
        return False

    sources = [user_data]
    for key in ("user_metadata", "app_metadata"):
        metadata = user_data.get(key)
        if isinstance(metadata, dict):
            sources.append(metadata)

    roles = {
        str(source["role"]).strip().lower() for source in sources if source.get("role")
    }
    if required_permission == "admin" and roles.intersection(
        {"admin", "administrador"}
    ):
        return True

    if required_permission in CATALOG_ACTIONS.values():
        for role in roles:
            if check_catalog_permission(role, required_permission):
                return True

    permissions = []
    for source in sources:
        value = source.get("permissions")
        if isinstance(value, str):
            permissions.extend(value.split(","))
        elif isinstance(value, (list, tuple, set)):
            permissions.extend(value)

    permission_values = {str(item).strip() for item in permissions if str(item).strip()}
    if required_permission == CATALOG_ACTIONS["READ"]:
        permission_values.add("catalog:view")
    return required_permission in permission_values
