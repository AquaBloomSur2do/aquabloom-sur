from app.database import supabase
from fastapi import APIRouter, HTTPException, Query, status

from .schemas import SampleListResponse

router = APIRouter(prefix="/api/v1/samples", tags=["Samples"])


@router.get("", response_model=SampleListResponse)
async def list_samples(
    quarantine: bool | None = Query(None, description="Filtrar por estado de cuarentena (true/false)"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Tamaño de página")
):
    
    offset = (page - 1) * page_size
    limit = offset + page_size - 1

    try:
        query = supabase.table("samples").select("*", count="exact")

        if quarantine is not None:
            query = query.eq("is_quarantined", quarantine)

        query = query.range(offset, limit)
        response = query.execute()
        
        return SampleListResponse(
            items=response.data,
            total=response.count if response.count is not None else 0,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar las muestras: {e!s}"
        )
    