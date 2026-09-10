from supabase import Client, create_client

from app.config import settings

# Instancia directa y única del cliente (Make it Work)
supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_KEY
)

def check_supabase_connection() -> dict:
    """
    Ejecuta una consulta mínima de solo lectura para validar la conexión.
    Falla de forma controlada si hay error de credenciales o red.
    """
    try:
        # Consulta ligera: extrae un solo ID de la tabla perfiles (creada en S2-013)
        supabase.table("profiles").select("id").limit(1).execute()
        return {"status": "ok", "connection": "successful"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": str(e)}