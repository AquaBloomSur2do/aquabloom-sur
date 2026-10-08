from uuid import UUID

from pydantic import BaseModel, Field


class SceneRegistration(BaseModel):
    lake_id: UUID = Field(..., description="Identificador del lago asociado")
    external_id: str = Field(..., description="Identificador externo del producto")
    provider: str = Field(..., description="Procedencia u origen de la escena satelital")

    model_config = {
        "json_schema_extra": {
            "example": {
                "lake_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "external_id": "S2B_MSIL2A_20260818T143000_N0509_R053_T18HYC_20260818T164500",
                "provider": "Copernicus Data Space"
            }
        }
    }


class SceneDetail(SceneRegistration):
    id: UUID = Field(..., description="Identificador interno de la escena en AquaBloom Sur")
    cloud_cover: float | None = Field(None, description="Porcentaje de nubosidad")
    status: str = Field(..., description="Estado de procesamiento")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "a1b2c3d4-e5f6-7890-1234-56789abcdef0",
                "lake_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "external_id": "S2B_MSIL2A_20260818T143000_N0509_R053_T18HYC_20260818T164500",
                "provider": "Copernicus Data Space",
                "cloud_cover": 12.5,
                "status": "processed"
            }
        }
    }


class SceneList(BaseModel):
    items: list[SceneDetail]
    total: int
    page: int
    page_size: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "id": "a1b2c3d4-e5f6-7890-1234-56789abcdef0",
                        "lake_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                        "external_id": "S2B_MSIL2A_20260818T143000_N0509_R053_T18HYC_20260818T164500",
                        "provider": "Copernicus Data Space",
                        "cloud_cover": 12.5,
                        "status": "processed"
                    }
                ],
                "total": 145,
                "page": 1,
                "page_size": 20
            }
        }
    }
    