from typing import NoReturn

from fastapi import HTTPException, status

try:
    from postgrest.exceptions import APIError
except (ImportError, ModuleNotFoundError):
    try:
        from supabase.lib.client_options import APIError
    except (ImportError, ModuleNotFoundError):

        class APIError(Exception):
            code: str = "500"

            def __init__(self, error: object = None):
                super().__init__(error)
                if isinstance(error, dict):
                    self.code = str(error.get("code", self.code))


def raise_database_error(exc: Exception) -> NoReturn:
    error_code = getattr(exc, "code", None)
    if str(error_code) == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La decisión entra en conflicto con un registro existente.",
        ) from exc
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la pertenencia de escena o el dataset relacionado.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo completar la operación de revisión del dataset.",
    ) from exc


def raise_publication_database_error(exc: Exception) -> NoReturn:
    error_code = getattr(exc, "code", None)
    if str(error_code) == "PGRST116":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión del dataset no existe.",
        ) from exc
    if str(error_code) == "42501":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para publicar esta versión.",
        ) from exc
    if str(error_code) in {"23503", "23505"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo publicar la versión por un conflicto de datos.",
        ) from exc
    if str(error_code) == "22P02":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El identificador de versión no es válido.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo publicar la versión.",
    ) from exc


def execute_database_query(query):
    try:
        return query.execute()
    except APIError as exc:
        raise_database_error(exc)
    except Exception as exc:  # noqa: BLE001
        raise_database_error(exc)


def fetch_rows(query) -> list[dict]:
    response = execute_database_query(query)
    return response.data or []


def fetch_page_rows(query, page_size: int) -> tuple[list[dict], bool]:
    rows = fetch_rows(query)
    return rows[:page_size], len(rows) > page_size


def fetch_manifest_sources_with_fallback(client) -> list[dict]:
    try:
        scenes_res = (
            client.table("scenes")
            .select("id, provider, capture_date")
            .limit(50)
            .execute()
        )
        return scenes_res.data if scenes_res.data else []
    except Exception:  # noqa: BLE001
        return [{"id": "src-fallback", "provider": "Sentinel-2", "status": "mock"}]


def fetch_manifest_observations_with_fallback(client) -> list[dict]:
    try:
        obs_res = (
            client.schema("satellite")
            .table("spectral_observations")
            .select("id, scene_id, sample_id, spectral_index, index_value")
            .limit(50)
            .execute()
        )
        return obs_res.data if obs_res.data else []
    except Exception:  # noqa: BLE001
        return [{"id": "obs-fallback", "spectral_index": "NDVI", "index_value": 0.65}]


def fetch_manifest_samples_with_fallback(client) -> list[dict]:
    try:
        samples_res = (
            client.table("samples").select("id, station_id").limit(50).execute()
        )
        return samples_res.data if samples_res.data else []
    except Exception:  # noqa: BLE001
        return [{"id": "rec-fallback", "value": "demo"}]
