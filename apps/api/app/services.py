from uuid import UUID

from fastapi import HTTPException


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
        raise HTTPException(status_code=404, detail="Lago no encontrado")
        
    return response.data[0]
