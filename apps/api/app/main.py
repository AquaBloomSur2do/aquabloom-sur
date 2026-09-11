from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# Metadatos de las etiquetas para Swagger
tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Auth", "description": "Autenticación de usuarios."},
    {"name": "Catalog", "description": "Catálogo de lagos y estaciones."}
]

app = FastAPI(
    title="AquaBloom Sur API",
    description="API REST para el manejo de usuarios, control de roles y catálogo de lagos.",
    servers=[{"url": "http://localhost:8000"}],
    openapi_tags=tags_metadata
)

# Habilitar CORS para que el frontend React 
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "API inicializada correctamente"}

@app.get("/api/v1/health", tags=["System"])
def health_check():
    return {
        "service": "AquaBloom Sur API",
        "version": "v1",
        "status": "ok"
    }
