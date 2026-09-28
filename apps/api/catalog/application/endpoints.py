import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .schemas import StationCreate

# Si prefieres importar el engine desde tu archivo de configuración, descomenta la siguiente línea:
# from app.config import settings

# Configuración del motor y la sesión (ajusta tu DATABASE_URL según corresponda)
# engine = create_engine(settings.DATABASE_URL)
engine = create_engine("postgresql://usuario:password@localhost/tu_base_de_datos")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

router = APIRouter()


def get_db():
    """Dependencia de FastAPI para obtener una sesión de base de datos por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/api/v1/lakes/{lake_id}/stations", status_code=201)
def create_station(
    lake_id: uuid.UUID, payload: StationCreate, db: Session = Depends(get_db) # noqa: B008
):
    """Crea una nueva estación asociada a un lago.

    Implementa validación de código único y geometría espacial SRID 4326.
    """
    # 1. Validación (409 Conflict): Verificar si el código ya existe para el lake_id
    query_check = text(
        "SELECT id FROM catalog.station WHERE lake_id = :lake_id AND code = :code"
    )
    existing = db.execute(
        query_check, {"lake_id": str(lake_id), "code": payload.code}
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="El código de la estación ya existe para este lago.",
        )

    # 2. Geometría espacial (PostGIS): Inserción explícita con SRID 4326
    query_insert = text("""
        INSERT INTO catalog.station (lake_id, code, name, source, activity, geom)
        VALUES (
            :lake_id, 
            :code, 
            :name, 
            :source,
            :activity,
            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)
        )
        RETURNING id;
    """)

    result = db.execute(
        query_insert,
        {
            "lake_id": str(lake_id),
            "code": payload.code,
            "name": payload.name,
            "source": payload.source,
            "activity": payload.activity,
            "longitude": payload.longitude,
            "latitude": payload.latitude,
        },
    )

    station_id = result.scalar()
    db.commit()

    return {"id": station_id, "message": "Estación creada exitosamente."}
