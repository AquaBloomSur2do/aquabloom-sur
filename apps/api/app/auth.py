from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .database import supabase
from .services import get_current_user_profile

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    status: str


class MembershipResponse(BaseModel):
    id: UUID
    role: str
    status: str
    organization: OrganizationResponse


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str | None
    memberships: list[MembershipResponse]


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un token de autenticacion",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(token: str = Depends(get_bearer_token)):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de autenticacion no esta disponible",
        )

    try:
        auth_response = supabase.auth.get_user(token)
        user = auth_response.user
        user_id = UUID(str(user.id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticacion invalido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return get_current_user_profile(supabase, user_id, user.email)
