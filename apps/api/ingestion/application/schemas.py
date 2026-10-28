from pydantic import BaseModel, field_validator


class ImportCreate(BaseModel):
    srid: int
    chlorophyll_a: float

    @field_validator("srid")
    def validate_srid(cls, v):
        if v != 4326:
            raise ValueError("El SRID debe ser exactamente 4326")
        return v
        
    @field_validator("chlorophyll_a")
    def validate_chlorophyll(cls, v):
        if v < 0:
            raise ValueError("chlorophyll_a no puede ser negativo")
        return v
    