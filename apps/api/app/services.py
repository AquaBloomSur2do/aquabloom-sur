from uuid import UUID

from fastapi import HTTPException, status
from shapely.geometry import Point, shape


def validate_station_inside_lake(lake_geojson: dict, lat: float, lon: float) -> None:
    # Shapely utiliza el formato (Longitud, Latitud)
    station_point = Point(lon, lat)
    lake_polygon = shape(lake_geojson)

    if not lake_polygon.contains(station_point):
        raise ValueError("Las coordenadas de la estación están fuera del polígono del lago.")

def get_current_user_profile(supabase, user_id: UUID, email: str) -> dict:
    # 1. Operación Atómica para evitar condiciones de carrera (Ticket S2-036).
    # Se preserva el identificador original de Supabase Auth inyectándolo en 'id'.
    # Si dos peticiones llegan al mismo milisegundo, PostgreSQL ignora la segunda.
    supabase.table("profiles").upsert(
        {"id": str(user_id), "email": email}, on_conflict="id", ignore_duplicates=True
    ).execute()

    # 2. Recuperación del perfil y sus relaciones (roles/organizaciones).
    # Mapea con la estructura de respuesta (CurrentUserResponse) definida en auth.py.
    response = (
        supabase.table("profiles")
        .select("id, email, memberships(role, status, organization(id, name, status))")
        .eq("id", str(user_id))
        .single()
        .execute()
    )

    return response.data

def add_organization_member(supabase, org_id: UUID, profile_id: UUID, role: str) -> dict:
    # 1. Validar: Perfil inexistente
    profile_res = supabase.table("profiles").select("id").eq("id", str(profile_id)).execute()
    if not profile_res.data:
        raise LookupError("Perfil inexistente")
        
    # 2. Validar: Membresía duplicada
    member_res = supabase.table("memberships").select("id").eq("organization_id", str(org_id)).eq("profile_id", str(profile_id)).execute()
    if member_res.data:
        raise ValueError("Membresia duplicada en esta organización")
        
    # 3. Validar: Administrador de otra organización
    if role == "admin":
        admin_res = supabase.table("memberships").select("id").eq("profile_id", str(profile_id)).eq("role", "admin").neq("organization_id", str(org_id)).execute()
        if admin_res.data:
            raise ValueError("El usuario ya es administrador de otra organización")

    # 4. Insertar la nueva membresía
    insert_res = supabase.table("memberships").insert({
        "organization_id": str(org_id),
        "profile_id": str(profile_id),
        "role": role,
        "status": "active"
    }).execute()
    
    return insert_res.data[0]
def get_lake_by_id(supabase, lake_id: UUID) -> dict:
    response = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()
    
    # Lago inexistente (Error 404)
    if not response.data:
        raise LookupError("Lago no encontrado")       
    return response.data[0]

def create_organization(supabase, org_data: dict) -> dict:
    try:
        response = supabase.table("organizations").insert(org_data).execute()
        return response.data[0]
    except Exception as exc:
        error_msg = str(exc).lower()
        # PostgREST devuelve errores 23505 para violaciones UNIQUE
        if "duplicate key" in error_msg or "unique constraint" in error_msg or "23505" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una organización con ese identificador o nombre."
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear la organización: {exc!s}"
        ) from exc
