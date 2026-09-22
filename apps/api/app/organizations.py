from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Security, status
from pydantic import BaseModel

from .auth import verify_supabase_jwt
from .database import supabase
from .services import get_organization_members_for_user

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


class OrganizationMemberResponse(BaseModel):
    user_id: UUID
    profile_id: UUID | None = None
    full_name: str | None = None
    email: str | None = None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


@router.get(
    "/{organization_id}/members", response_model=list[OrganizationMemberResponse]
)
def list_organization_members(
    organization_id: UUID,
    payload: dict = Security(verify_supabase_jwt),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de autenticación no está disponible",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario (sub).",
        )

    current_user_id = UUID(str(user_id))

    try:
        members = get_organization_members_for_user(
            supabase, current_user_id, organization_id
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return members
