from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_supabase_jwt
from app.database import supabase
from app.schemas import MembershipCreate
from app.services import add_organization_member

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


# Definición estricta del esquema de respuesta (S2-040)
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


@router.post("/api/v1/organizations/{id}/members", tags=["Organizations"])
def create_organization_member(
    id: UUID, 
    membership: MembershipCreate,
    user=Depends(verify_supabase_jwt) # noqa: B008
):
    try:
        return add_organization_member(
            supabase=supabase,
            org_id=id,
            profile_id=membership.profile_id,
            role=membership.role
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    