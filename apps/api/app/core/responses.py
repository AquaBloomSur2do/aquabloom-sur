COMMON_ERRORS = {
    401: {
        "description": "No autenticado",
        "content": {
            "application/json": {
                "example": {
                    "code": "UNAUTHORIZED",
                    "message": "Token inválido o expirado",
                    "details": {},
                    "request_id": "req-123abc",
                }
            }
        },
    },
    403: {
        "description": "Permiso insuficiente",
        "content": {
            "application/json": {
                "example": {
                    "code": "FORBIDDEN",
                    "message": "No tienes permiso catalog:create",
                    "details": {},
                    "request_id": "req-124def",
                }
            }
        },
    },
    404: {
        "description": "Recurso no encontrado",
        "content": {
            "application/json": {
                "example": {
                    "code": "NOT_FOUND",
                    "message": "El recurso solicitado no existe",
                    "details": {"id": "123e4567-e89b-12d3-a456-426614174000"},
                    "request_id": "req-125ghi",
                }
            }
        },
    },
    409: {
        "description": "Conflicto",
        "content": {
            "application/json": {
                "example": {
                    "code": "CONFLICT",
                    "message": "El registro ya existe",
                    "details": {"code": "EST-01"},
                    "request_id": "req-126jkl",
                }
            }
        },
    },
    422: {
        "description": "Error de validación",
        "content": {
            "application/json": {
                "example": {
                    "code": "VALIDATION_ERROR",
                    "message": "Datos de entrada inválidos",
                    "details": {"latitude": "Debe ser mayor o igual a -90"},
                    "request_id": "req-127mno",
                }
            }
        },
    },
}
