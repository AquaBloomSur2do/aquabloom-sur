import logging

from supabase import Client, create_client

from app.config import settings

logger = logging.getLogger(__name__)

def get_supabase_client() -> Client | None:
    """Crea el cliente evaluando los atributos reales de Settings sin detener la API."""
    try:
        # Extracción dinámica previendo inconsistencias en Pydantic Settings
        url = getattr(settings, "SUPABASE_URL", getattr(settings, "supabase_url", None))
        key = getattr(settings, "SUPABASE_SERVICE_KEY", getattr(settings, "supabase_key", None))

        if not url or not key:
            logger.warning("Credenciales de Supabase ausentes o mal nombradas en el entorno.")
            return None

        return create_client(supabase_url=url, supabase_key=key)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Fallo crítico al inicializar cliente Supabase: {e}")
        return None

# Instancia segura
supabase = get_supabase_client()

def check_supabase_connection() -> dict:
    """Diagnóstico explícito sin exponer claves ni trazas sensibles."""
    if not supabase:
        return {"status": "error", "detail": "Cliente inactivo por falta de credenciales."}
    
    try:
        supabase.table("profiles").select("id").limit(1).execute()
        return {"status": "ok", "connection": "successful"}
    except Exception:  # noqa: BLE001
        return {"status": "error", "detail": "Fallo de red o permisos insuficientes."}