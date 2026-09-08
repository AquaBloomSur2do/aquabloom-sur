from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Definición de etiquetas para organizar Swagger
tags_metadata = [
    {"name": "System", "description": "Operaciones del sistema y estado de salud."},
    {"name": "Auth", "description": "Autenticación y gestión de usuarios."},
    {"name": "Catalog", "description": "Catálogo de lagos y estaciones."}
]

app = FastAPI(
    title="AquaBloom Sur API",
    description="API para la plataforma de estimación de clorofila-a.",
    version="1.0.0",
    openapi_tags=tags_metadata,
    servers=[{"url": "http://localhost:8000", "description": "Servidor Local"}]
)

# Habilitar CORS
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
    return {
        "service": "AquaBloom Sur API",
        "version": "1.0.0",
        "status": "ok"
    }
