from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


def mock_get_current_user(authorization: Annotated[str | None, Header()] = None) -> dict | None:
    """Mock temporal para evaluar el criterio de aceptación del ticket."""
    if not authorization:
        return None
    if authorization == "Bearer token-admin":
        return {"id": "1", "role": "admin"}
    if authorization == "Bearer token-empleado":
        return {"id": "2", "role": "empleado"}
    
    return None


def require_permission(required_role: str) -> Callable:
    """
    Fábrica de dependencias que protege los endpoints según el rol del usuario.
    """
    def role_checker(current_user: Annotated[dict | None, Depends(mock_get_current_user)]) -> dict:
        # Criterio: Devuelve 401 al usuario anónimo
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Criterio: Devuelve 403 al rol insuficiente
        if current_user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes"
            )
        
        # Criterio: Permite al rol autorizado
        return current_user
        
    return role_checker
