import jwt
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from .database import supabase
from .services import get_current_user_profile

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)
security = HTTPBearer()

class AuthException(Exception):
    def __init__(self, message: str, details: dict):
        self.message = message
        self.details = details

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

def verify_supabase_jwt(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict: # noqa: B008
    token = credentials.credentials
    secret = settings.supabase_jwt_secret
    issuer = f"{settings.supabase_url}/auth/v1"
    
    try:
        # Decodificación estricta: firma, expiración, emisor y audiencia
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            issuer=issuer
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthException("El token JWT ha expirado.", {"code": "TOKEN_EXPIRED"})
    except jwt.InvalidAudienceError:
        raise AuthException("Audiencia del token inválida.", {"code": "INVALID_AUDIENCE"})
    except jwt.InvalidIssuerError:
        raise AuthException("Emisor del token inválido.", {"code": "INVALID_ISSUER"})
    except jwt.PyJWTError:
        raise AuthException("Token JWT alterado o inválido.", {"code": "INVALID_TOKEN"})

def get_bearer_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str: # noqa: B008
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
