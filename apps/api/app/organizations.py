from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import require_admin, verify_supabase_jwt
from app.database import supabase
from app.schemas import OrganizationCreate, OrganizationOut
from app.services import create_organization

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


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_org(org: OrganizationCreate, payload: dict = Depends(require_admin)):  # noqa: B008
    org_data = {
        "name": org.name,
        "identifier": org.identifier,
        "description": org.description,
        "status": "active"
    }
    return create_organization(supabase, org_data)

