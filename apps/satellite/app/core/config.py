from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "AquaBloom Satellite"
    environment: str = "development"
    redis_url: str = "redis://localhost:6379/0"
    internal_service_token: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SATELLITE_",
        extra="ignore",
    )


settings = Settings()
