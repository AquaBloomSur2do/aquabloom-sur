from unittest.mock import MagicMock
from uuid import UUID

from apps.scientific.app.domains.identity.service_identity import (
    get_current_user_profile,
)


def test_get_current_user_profile_uses_scientific_database_client():
    client = MagicMock()
    user_id = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    memberships = [
        {
            "id": "membership-1",
            "role": "investigador",
            "status": "active",
        }
    ]
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
        memberships
    )

    profile = get_current_user_profile(client, user_id, "user@example.test")

    assert profile == {
        "id": str(user_id),
        "email": "user@example.test",
        "memberships": memberships,
    }
    client.table.assert_any_call("profiles")
    client.table.assert_any_call("memberships")
    client.table.return_value.upsert.assert_called_once_with(
        {"id": str(user_id), "email": "user@example.test"},
        on_conflict="id",
        ignore_duplicates=True,
    )
