from uuid import UUID

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


def get_lakes(
    client: Client,
    *,
    text: str | None = None,
    region: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """Devuelve únicamente los lagos activos, salvo que se pida un filtro concreto."""
    query = client.table("lakes").select("*", count="exact")

    if status_filter:
        query = query.eq("status", status_filter)
    else:
        query = query.eq("status", "active")

    if text:
        query = query.ilike("name", f"%{text}%")
    if region:
        query = query.eq("region", region)

    start = (page - 1) * limit
    end = start + limit - 1
    query = query.range(start, end)

    response = query.execute()
    return {
        "items": response.data or [],
        "page": page,
        "page_size": limit,
        "total": response.count if response.count is not None else 0,
    }


def get_lake_by_id(client: Client, lake_id: UUID, *, include_inactive: bool = False) -> dict:
    """Recupera un lago por id y evita devolver registros inactivos salvo explícito."""
    query = client.table("lakes").select("*").eq("id", str(lake_id))
    if not include_inactive:
        query = query.eq("status", "active")

    response = query.execute()
    if not response.data:
        raise LookupError("Lago no encontrado")
    return response.data[0]


def soft_delete_lake(client: Client, lake_id: UUID) -> dict:
    """Desactiva un lago sin eliminar físicamente el registro."""
    response = (
        client.table("lakes")
        .update({"status": "inactive"})
        .eq("id", str(lake_id))
        .execute()
    )
    if not response.data:
        raise LookupError("Lago no encontrado")
    return response.data[0]


