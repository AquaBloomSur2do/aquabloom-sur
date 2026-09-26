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
