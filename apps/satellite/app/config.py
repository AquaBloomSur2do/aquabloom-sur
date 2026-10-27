from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "AquaBloom Satellite"
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SATELLITE_",
        extra="ignore",
    )


settings = Settings()
