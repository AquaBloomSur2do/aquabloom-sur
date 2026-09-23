from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import AuthException
from app.auth import router as auth_router
from app.config import settings
from app.database import check_supabase_connection, supabase
from app.handlers import auth_exception_handler, global_exception_handler
from app.organizations import router as organizations_router
from app.schemas import MembershipCreate
from app.services import add_organization_member

tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Auth", "description": "Autenticación de usuarios."},
    {"name": "Organizations", "description": "Gestión de organizaciones."}, # <-- Añadir
    {"name": "Catalog", "description": "Catálogo de lagos y estaciones."},
    {
        "name": "Organizations",
        "description": "Gestión de organizaciones de usuarios.",
    },  # Documentación actualizada
]

app = FastAPI(
    title="AquaBloom Sur API",
    description="API REST para el manejo de usuarios, control de roles y catálogo de lagos.",
    servers=[{"url": "http://localhost:8000"}],
    openapi_tags=tags_metadata,
)

app.add_exception_handler(AuthException, auth_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(auth_router)
app.include_router(organizations_router)

# Habilitar CORS para el frontend React
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

@app.post("/api/v1/organizations/{id}/members", tags=["Organizations"])
def create_organization_member(id: UUID, membership: MembershipCreate):
    return add_organization_member(
        supabase=supabase,
        org_id=id,
        profile_id=membership.profile_id,
        role=membership.role
    )
