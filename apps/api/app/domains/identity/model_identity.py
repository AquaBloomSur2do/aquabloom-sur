from uuid import UUID

from apps.api.app.core.permissions import has_permission
from supabase import Client


def get_active_memberships(client: Client, user_id: UUID) -> list[dict]:
    """Return only active memberships belonging to active organizations."""
    response = (
        client.table("memberships")
        .select("id, role, status, organization:organizations!inner(id, name, status)")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .execute()
    )
    return response.data or []


def count_active_lakes(client: Client) -> int:
    response = (
        client.table("lakes")
        .select("id", count="exact", head=True)
        .eq("status", "active")
        .execute()
    )
    return response.count or 0


def count_active_stations(client: Client) -> int:
    response = (
        client.table("stations")
        .select("id", count="exact", head=True)
        .eq("status", "active")
        .execute()
    )
    return response.count or 0


def count_visible_organizations(client: Client, user_data: dict) -> int:
    if has_permission(user_data, "admin"):
        response = (
            client.table("organizations")
            .select("id", count="exact", head=True)
            .eq("status", "active")
            .execute()
        )
        return response.count or 0

    user_id = user_data.get("sub") or user_data.get("id")
    if not user_id:
        return 0

    response = (
        client.table("memberships")
        .select("organization_id, organizations!inner(id)", count="exact", head=True)
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .execute()
    )
    return response.count or 0


def upsert_user_profile(client: Client, user_id: UUID, email: str | None) -> None:
    try:
        client.table("profiles").upsert(
            {"id": str(user_id), "email": email},
            on_conflict="id",
            ignore_duplicates=True,
        ).execute()
    except Exception:  # noqa: BLE001, S110
        pass


def list_all_profiles_ordered(client: Client) -> list[dict]:
    response = (
        client.table("profiles").select("id, email, name").order("name").execute()
    )
    return response.data or []


def list_user_organizations_from_db(client: Client, user_id: str) -> list[dict]:
    response = (
        client.table("memberships")
        .select("role, organizations!inner(id, name)")
        .eq("user_id", user_id)
        .execute()
    )
    organizations_list = []
    for item in response.data or []:
        org_data = item.get("organizations", {})
        organizations_list.append(
            {
                "id": org_data.get("id"),
                "name": org_data.get("name"),
                "role": item.get("role"),
            }
        )
    return organizations_list


def get_organization_by_id(client: Client, organization_id: UUID) -> dict | None:
    res = (
        client.table("organizations")
        .select("id, name, status")
        .eq("id", str(organization_id))
        .maybe_single()
        .execute()
    )
    return res.data if res else None


def get_active_membership_for_user(
    client: Client, user_id: UUID, organization_id: UUID
) -> dict | None:
    res = (
        client.table("memberships")
        .select("id, role, status")
        .eq("user_id", str(user_id))
        .eq("organization_id", str(organization_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    return res.data if res else None


def list_organization_memberships(client: Client, organization_id: UUID) -> list[dict]:
    response = (
        client.table("memberships")
        .select("id, user_id, role, status, created_at, updated_at")
        .eq("organization_id", str(organization_id))
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def get_profiles_by_ids(client: Client, user_ids: list[str]) -> list[dict]:
    if not user_ids:
        return []
    res = (
        client.table("profiles")
        .select("id, email, name")
        .in_("id", user_ids)
        .execute()
    )
    return res.data or []


def profile_exists(client: Client, profile_id: UUID) -> bool:
    res = client.table("profiles").select("id").eq("id", str(profile_id)).execute()
    return bool(res.data)


def membership_exists(client: Client, org_id: UUID, profile_id: UUID) -> bool:
    res = (
        client.table("memberships")
        .select("id")
        .eq("organization_id", str(org_id))
        .eq("user_id", str(profile_id))
        .execute()
    )
    return bool(res.data)


def is_admin_in_other_organization(
    client: Client, profile_id: UUID, excluded_org_id: UUID
) -> bool:
    res = (
        client.table("memberships")
        .select("id")
        .eq("user_id", str(profile_id))
        .eq("role", "admin")
        .neq("organization_id", str(excluded_org_id))
        .execute()
    )
    return bool(res.data)


def insert_membership(
    client: Client, org_id: UUID, profile_id: UUID, role: str
) -> dict:
    insert_res = (
        client.table("memberships")
        .insert(
            {
                "organization_id": str(org_id),
                "user_id": str(profile_id),
                "role": role,
                "status": "active",
            }
        )
        .execute()
    )
    return insert_res.data[0]


def insert_organization(client: Client, org_data: dict) -> dict:
    response = client.table("organizations").insert(org_data).execute()
    return response.data[0]


def insert_audit_log(
    client: Client,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    try:
        client.table("audit_logs").insert(
            {
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "details": details or {},
            }
        ).execute()
    except Exception as e:  # noqa: BLE001
        print(f"Alerta: Fallo silencioso en auditoría: {e}")
        
