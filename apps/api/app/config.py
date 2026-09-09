from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Variables con valores por defecto (opcionales)
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"
    
    # Variables obligatorias (sin valor por defecto)
    supabase_url: str
    supabase_anon_key: str

    # Nueva configuración para Pydantic V2
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Instanciamos la configuración para poder usarla en el resto de la API
settings = Settings()
