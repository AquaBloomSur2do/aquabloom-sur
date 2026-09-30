import pytest
from app.permissions import CATALOG_ACTIONS, check_catalog_permission


def test_explicit_roles_permissions():
    """Valida que los 4 roles tengan sus permisos explícitos correctamente asignados."""
    # Administrador tiene acceso total
    assert check_catalog_permission("administrador", CATALOG_ACTIONS["DISABLE"]) is True
    assert check_catalog_permission("administrador", CATALOG_ACTIONS["READ"]) is True

    # Supervisor puede actualizar pero no deshabilitar
    assert check_catalog_permission("supervisor", CATALOG_ACTIONS["UPDATE"]) is True
    assert check_catalog_permission("supervisor", CATALOG_ACTIONS["DISABLE"]) is False

    # Investigador puede crear pero no actualizar
    assert check_catalog_permission("investigador", CATALOG_ACTIONS["CREATE"]) is True
    assert check_catalog_permission("investigador", CATALOG_ACTIONS["UPDATE"]) is False

    # Auditor es de solo lectura
    assert check_catalog_permission("auditor", CATALOG_ACTIONS["READ"]) is True
    assert check_catalog_permission("auditor", CATALOG_ACTIONS["CREATE"]) is False


def test_unknown_action_rejection():
    """Prueba obligatoria (S2-037): Detectar y rechazar acciones desconocidas."""
    with pytest.raises(
        ValueError, match="Acción de seguridad desconocida o no válida: catalog:delete"
    ):
        check_catalog_permission("administrador", "catalog:delete")

    with pytest.raises(
        ValueError,
        match="Acción de seguridad desconocida o no válida: catalog:drop_table",
    ):
        check_catalog_permission("investigador", "catalog:drop_table")
