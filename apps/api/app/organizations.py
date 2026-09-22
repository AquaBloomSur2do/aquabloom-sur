from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_supabase_jwt

# Importamos la instancia de BD y la barrera de seguridad de tu compañero
from app.database import supabase

# Definimos el router con la ruta base exigida en el ticket
router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


# Definición estricta del esquema de respuesta (Criterio de Aceptación)
class UserOrganizationResponse(BaseModel):
    id: UUID
    name: str
    role: str


@router.get("/", response_model=list[UserOrganizationResponse])
def get_user_organizations(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    """
    Recupera las organizaciones exclusivas del usuario autenticado.
    Impide la enumeración de organizaciones a las que no pertenece.
    """
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario no encontrado en el token.",
        )

    try:
        # Consulta a la tabla intermedia 'memberships' filtrando por el usuario exacto.
        # Esto cumple la directiva de impedir la enumeración de entidades ajenas.
        response = (
            supabase.table("memberships")
            .select("role, organizations!inner(id, name)")
            .eq("user_id", user_id)
            .execute()
        )

        # Mapeo de la respuesta relacional de Supabase al esquema plano requerido
        organizations_list = []
        for item in response.data:
            org_data = item.get("organizations", {})
            organizations_list.append(
                {
                    "id": org_data.get("id"),
                    "name": org_data.get("name"),
                    "role": item.get("role"),
                }
            )

        return organizations_list

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al recuperar organizaciones: {exc}",
        ) from exc
