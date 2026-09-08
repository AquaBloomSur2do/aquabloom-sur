from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AquaBloom Sur API")

# Habilitar CORS para que el frontend React de tus compañeros pueda conectarse
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

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AquaBloom Sur API"}