from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Security, status
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


def verify_supabase_jwt(
    credentials: HTTPAuthorizationCredentials = Security(security), #noqa: B008
) -> dict:
    token = credentials.credentials
    secret = settings.supabase_jwt_secret
    issuer = f"{settings.supabase_url}/auth/v1"

    try:
        # Decodificación estricta: firma, expiración, emisor y audiencia
        payload = jwt.decode(
            token, secret, algorithms=["HS256"], audience="authenticated", issuer=issuer
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthException("El token JWT ha expirado.", {"code": "TOKEN_EXPIRED"})
    except jwt.InvalidAudienceError:
        raise AuthException(
            "Audiencia del token inválida.", {"code": "INVALID_AUDIENCE"}
        )
    except jwt.InvalidIssuerError:
        raise AuthException("Emisor del token inválido.", {"code": "INVALID_ISSUER"})
    except jwt.PyJWTError:
        raise AuthException("Token JWT alterado o inválido.", {"code": "INVALID_TOKEN"})


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(payload: dict = Security(verify_supabase_jwt)):  # noqa: B008
    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        raise AuthException(
            "Token sin identificador de usuario (sub).", {"code": "MISSING_SUB"}
        )

    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    try:
        # Pasamos el UUID validado localmente al servicio de perfiles existente.
        # Cero llamadas de red al servidor de Auth de Supabase.
        return get_current_user_profile(supabase, UUID(user_id), email)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al recuperar el perfil: {exc!s}",
        )


def require_admin(payload: dict = Security(verify_supabase_jwt)) -> dict:  # noqa: B008
    user_metadata = payload.get("user_metadata", {})
    role = user_metadata.get("role")
    
    if role != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden realizar esta acción."
        )
    return payload

ROLE_PERMISSIONS = {
    "administrador": ["catalog:view", "catalog:update", "catalog:disable"],
    "investigador": ["catalog:view", "catalog:update"],
    "usuario": ["catalog:view"],
}


def _has_permission(payload: dict, required_permission: str) -> bool:
    user_metadata = payload.get("user_metadata", {})
    role = user_metadata.get("role")
    if not role:
        return False
    return required_permission in ROLE_PERMISSIONS.get(role, [])

def require_catalog_update_permission(payload: dict = Security(verify_supabase_jwt)) -> dict:  # noqa: B008
    if not _has_permission(payload, "catalog:update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar lagos."
        )
    return payload


