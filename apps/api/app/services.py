from uuid import UUID

from shapely.geometry import Point, shape


def validate_station_inside_lake(lake_geojson: dict, lat: float, lon: float) -> None:
    station_point = Point(lon, lat)
    lake_polygon = shape(lake_geojson)
    if not lake_polygon.contains(station_point):
        raise ValueError("Las coordenadas de la estación están fuera del polígono del lago.")

def add_organization_member(supabase, org_id: UUID, profile_id: UUID, role: str) -> dict:
    profile_res = supabase.table("profiles").select("id").eq("id", str(profile_id)).execute()
    if not profile_res.data:
        raise LookupError("Perfil inexistente")

    member_res = supabase.table("memberships").select("id").eq("organization_id", str(org_id)).eq("profile_id", str(profile_id)).execute()
    if member_res.data:
        raise ValueError("Membresía duplicada en esta organización")

    if role == "admin":
        admin_res = supabase.table("memberships").select("id").eq("profile_id", str(profile_id)).eq("role", "admin").neq("organization_id", str(org_id)).execute()
        if admin_res.data:
            raise ValueError("El usuario ya es administrador de otra organización")

    insert_res = supabase.table("memberships").insert({
        "organization_id": str(org_id),
        "profile_id": str(profile_id),
        "role": role,
        "status": "active"
    }).execute()
    return insert_res.data[0]

def create_organization(supabase, org_data: dict) -> dict:
    response = supabase.table("organizations").insert(org_data).execute()
    return response.data[0]

def log_audit_event(supabase, actor_id: str, action: str, resource_type: str, resource_id: str, details: dict | None = None) -> None:
    """Registra un evento de auditoría sin bloquear la transacción principal HTTP."""
    try:
        supabase.table("audit_logs").insert({
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "details": details or {}
        }).execute()
    except Exception as e:  # noqa: BLE001
        print(f"Alerta: Fallo silencioso en auditoría: {e}")

        