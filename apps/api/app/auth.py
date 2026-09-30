from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

from .database import supabase
from .permissions import CATALOG_ACTIONS, has_permission
from .services import get_current_user_profile

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)
ASYMMETRIC_JWT_ALGORITHMS = {"ES256", "RS256", "EdDSA"}


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


@lru_cache(maxsize=4)
def get_supabase_jwks_client(project_url: str) -> jwt.PyJWKClient:
    jwks_url = f"{project_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(jwks_url)


def verify_supabase_jwt(
    credentials: HTTPAuthorizationCredentials = Security(security),  # noqa: B008
) -> dict:
    token = credentials.credentials
    issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"

    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
        if algorithm == "HS256":
            secret = (
                settings.supabase_jwt_secret.get_secret_value()
                if hasattr(settings.supabase_jwt_secret, "get_secret_value")
                else settings.supabase_jwt_secret
            )
            if not secret:
                raise jwt.InvalidTokenError(
                    "No está configurado el secreto legacy para tokens HS256"
                )
            signing_key = secret
        elif algorithm in ASYMMETRIC_JWT_ALGORITHMS:
            signing_key = get_supabase_jwks_client(
                settings.supabase_url
            ).get_signing_key_from_jwt(token).key
        else:
            raise jwt.InvalidAlgorithmError("Algoritmo JWT no permitido")

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            audience="authenticated",
            issuer=issuer,
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


def optional_verify_supabase_jwt(
    credentials: HTTPAuthorizationCredentials | None = Security(optional_security),  # noqa: B008
) -> dict | None:
    if credentials is None:
        return None
    return verify_supabase_jwt(credentials)


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
        return get_current_user_profile(supabase, UUID(user_id), email)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al recuperar el perfil: {exc!s}",
        ) from exc


def require_admin(payload: dict = Security(verify_supabase_jwt)) -> dict:  # noqa: B008
    user_metadata = payload.get("user_metadata", {})
    role = user_metadata.get("role")

    if role != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden realizar esta acción.",
        )
    return payload


def require_catalog_create_permission(
    payload: dict = Security(verify_supabase_jwt),  # noqa: B008
) -> dict:
    if not has_permission(payload, CATALOG_ACTIONS["CREATE"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para crear lagos.",
        )
    return payload


def require_catalog_update_permission(
    payload: dict = Security(verify_supabase_jwt),  # noqa: B008
) -> dict:
    if not has_permission(payload, CATALOG_ACTIONS["UPDATE"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar lagos.",
        )
    return payload


def require_catalog_disable_permission(
    payload: dict = Security(verify_supabase_jwt),  # noqa: B008
) -> dict:
    if not has_permission(payload, CATALOG_ACTIONS["DISABLE"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para desactivar lagos.",
        )
    return payload

