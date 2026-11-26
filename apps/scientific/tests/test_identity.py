from unittest.mock import MagicMock
from uuid import UUID

from apps.scientific.app.domains.identity.service_identity import (
    get_current_user_profile,
)


def test_get_current_user_profile_uses_core_service_contract(monkeypatch):
    core_client = MagicMock()
    user_id = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    memberships = [
        {
            "id": "membership-1",
            "role": "investigador",
            "status": "active",
        }
    ]
    expected_profile = {
        "id": str(user_id),
        "email": "user@example.test",
        "memberships": memberships,
    }
    core_client.get_current_user_profile.return_value = expected_profile
    monkeypatch.setattr(
        "apps.scientific.app.domains.identity.model_identity.CoreServiceClient",
        lambda: core_client,
    )

    profile = get_current_user_profile(user_id, "user@example.test")

    assert profile == expected_profile
    core_client.get_current_user_profile.assert_called_once_with(
        user_id,
        "user@example.test",
    )
