from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SampleResponse(BaseModel):
    id: UUID = Field(..., description="Identificador interno de la muestra")
    station_id: UUID = Field(..., description="Estación donde se tomó la muestra")
    sample_datetime_utc: datetime = Field(..., description="Fecha y hora en UTC")
    chlorophyll_a_ug_l: float = Field(..., description="Concentración de clorofila-a")
    is_quarantined: bool = Field(..., description="Indica si la muestra está en cuarentena")
    quarantine_reason: str | None = Field(None, description="Motivo de la cuarentena si aplica")


class SampleListResponse(BaseModel):
    items: list[SampleResponse]
    total: int
    page: int
    page_size: int

    