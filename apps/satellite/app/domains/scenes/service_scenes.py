from datetime import date
from uuid import UUID

from apps.satellite.app.domains.scenes.domain_scenes import (
    is_valid_scene_date_range,
)
from apps.satellite.app.domains.scenes.model_scenes import (
    lake_exists_in_db,
    query_scenes_by_lake_and_dates,
)
from fastapi import HTTPException, status


def list_scenes_service(
    client,
    *,
    lake_id: UUID,
    start_date: date,
    end_date: date,
    page: int,
    page_size: int,
) -> dict:
    if not is_valid_scene_date_range(start_date, end_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio no puede ser posterior a la fecha de fin.",
        )

    if not lake_exists_in_db(client, lake_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lago no encontrado.",
        )

    offset = (page - 1) * page_size
    items, total = query_scenes_by_lake_and_dates(
        client,
        lake_id=lake_id,
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        page_size=page_size,
    )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }

