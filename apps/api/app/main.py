from app.auth import AuthException
from app.auth import router as auth_router
from app.config import settings
from app.database import check_supabase_connection
from app.dependencies import require_permission
from app.handlers import auth_exception_handler, global_exception_handler
from app.lakes import router as lakes_router
from app.organizations import router as organizations_router
from app.stations import router as stations_router
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Auth", "description": "Autenticación de usuarios."},
    {"name": "Organizations", "description": "Gestión de organizaciones de usuarios."},
    {"name": "Catalog", "description": "Catálogo de lagos y estaciones."},
]

app = FastAPI(
    title="AquaBloom Sur API",
    description="API REST para el manejo de usuarios, control de roles y catálogo de lagos.",
    version="v1",
    servers=[{"url": "http://localhost:8000"}],
    openapi_tags=tags_metadata,
)

# Habilitar CORS para el frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# --- Integración de Manejadores Globales (S2-008) ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Not Found" if exc.status_code == 404 else "HTTP Error",
            "message": str(exc.detail)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Parámetros de entrada inválidos",
            "details": exc.errors()
        }
    )

app.add_exception_handler(AuthException, auth_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(auth_router)
app.include_router(organizations_router)
app.include_router(lakes_router)
app.include_router(stations_router)

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

# --- Ruta de prueba para ticket S2-038 ---
@app.get("/api/test-permission", dependencies=[Depends(require_permission("admin"))], tags=["System"])
def test_permission_route() -> dict:
    return {"message": "Acceso permitido. Tienes el rol correcto."}
