from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import get_authenticated_user, get_bearer_token
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
    token: str = Depends(get_bearer_token),
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de autenticación no está disponible",
        )

    current_user_id, _ = get_authenticated_user(token)

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
