from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_supabase_connection

# Metadatos de las etiquetas para Swagger
tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Auth", "description": "Autenticación de usuarios."},
    {"name": "Catalog", "description": "Catálogo de lagos y estaciones."}
]

app = FastAPI(
    title="AquaBloom Sur API",
    description="API REST para el manejo de usuarios, control de roles y catálogo de lagos.",
    version="v1",
    servers=[{"url": "http://localhost:8000"}],
    openapi_tags=tags_metadata
)

# Habilitar CORS para que el frontend React 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "API inicializada correctamente"}


@app.get("/api/v1/health", tags=["System"])
def health_check():
    db_status = check_supabase_connection()
    return {
        "service": "AquaBloom Sur API",
        "version": "v1",
        "status": "ok" if db_status["status"] == "ok" else "degraded",
        "database": db_status
    }
