from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import AuthException
from app.auth import router as auth_router
from app.config import settings
from app.database import check_supabase_connection
from app.handlers import auth_exception_handler, global_exception_handler

# Metadatos de las etiquetas para Swagger
tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Auth", "description": "Autenticación de usuarios."},
    {"name": "Catalog", "description": "Catálogo de lagos y estaciones."},
]

app = FastAPI(
    title="AquaBloom Sur API",
    description="API REST para el manejo de usuarios, control de roles y catálogo de lagos.",
    servers=[{"url": "http://localhost:8000"}],
    openapi_tags=tags_metadata,
)

# Registro de manejadores de excepciones
app.add_exception_handler(AuthException, auth_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Registro de rutas
app.include_router(auth_router)

# Habilitar CORS para que el frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

@app.get("/")
def read_root():
    return {"message": f"API inicializada en ambiente: {settings.environment}"}

@app.get("/api/v1/health", tags=["System"])
def health_check():
    db_status = check_supabase_connection()
    return {
        "service": "AquaBloom Sur API",
        "version": "v1",
        "status": "ok" if db_status["status"] == "ok" else "degraded",
        "database": db_status,
    }