import jwt
from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

security = HTTPBearer()

class AuthException(Exception):
    def __init__(self, message: str, details: dict):
        self.message = message
        self.details = details

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
    
    