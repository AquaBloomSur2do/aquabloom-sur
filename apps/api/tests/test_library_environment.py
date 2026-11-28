import logging
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.config import settings
from apps.api.app.domains.library.domain_library import (
    LIBRARY_HEALTH_ROUTE,
    LIBRARY_READ_PERMISSION,
)
from apps.api.app.domains.library.service_library import (
    verify_library_module_startup,
)
from apps.api.app.main import app

client = TestClient(app)


def test_library_module_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "library_module_enabled", False)

    response = client.get(LIBRARY_HEALTH_ROUTE)

    assert response.status_code == 404
    assert response.json() == {
        "error": "Not Found",
        "message": "El módulo de biblioteca no está habilitado.",
    }


def test_library_module_requires_core_authentication_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "library_module_enabled", True)

    response = client.get(LIBRARY_HEALTH_ROUTE)

    assert response.status_code == 401
    assert response.json()["message"] == "Not authenticated"


def test_library_module_rejects_unauthorized_core_role(monkeypatch):
    monkeypatch.setattr(settings, "library_module_enabled", True)
    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: {"sub": "user-sin-permisos", "role": "invitado"},
    )

    response = client.get(LIBRARY_HEALTH_ROUTE)

    assert response.status_code == 403
    assert response.json()["message"] == "Permisos insuficientes"


@pytest.mark.parametrize(
    "user_payload",
    [
        {"sub": "admin-1", "role": "administrador"},
        {"sub": "sup-1", "role": "supervisor"},
        {"sub": "inv-1", "role": "investigador"},
        {"sub": "aud-1", "role": "auditor"},
        {"sub": "explicit-1", "permissions": [LIBRARY_READ_PERMISSION]},
    ],
)
def test_library_module_accepts_core_authorized_users_and_reports_startup(
    monkeypatch,
    user_payload,
):
    monkeypatch.setattr(settings, "library_module_enabled", True)
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: user_payload,
    )

    response = client.get(
        LIBRARY_HEALTH_ROUTE,
        headers={"X-Correlation-ID": "trace-library-s304"},
    )

    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "trace-library-s304"
    assert response.json() == {
        "module": "library",
        "status": "ready",
        "enabled": True,
        "environment": "test",
        "authorization": {
            "provider": "core_supabase_jwt_rbac",
            "required_permission": LIBRARY_READ_PERMISSION,
            "authenticated_subject": user_payload["sub"],
        },
        "routes": [LIBRARY_HEALTH_ROUTE],
    }


def test_verify_library_module_startup_logs_enabled_and_disabled_states(
    monkeypatch,
    caplog,
):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(settings, "library_module_enabled", True)

    startup_status = verify_library_module_startup(app)

    assert startup_status.module == "library"
    assert startup_status.status == "ready"
    assert startup_status.enabled is True
    assert LIBRARY_HEALTH_ROUTE in startup_status.routes
    assert any(
        "Arranque del módulo de biblioteca verificado" in record.getMessage()
        and "enabled=True" in record.getMessage()
        for record in caplog.records
    )

    monkeypatch.setattr(settings, "library_module_enabled", False)
    disabled_status = verify_library_module_startup(app)
    assert disabled_status.status == "disabled"
    assert disabled_status.enabled is False


def test_verify_library_module_startup_fails_if_router_not_mounted():
    bare_app = FastAPI()

    with pytest.raises(RuntimeError, match="no registró la ruta"):
        verify_library_module_startup(bare_app)


