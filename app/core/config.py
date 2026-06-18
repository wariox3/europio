from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "europio"
    environment: str = "development"
    debug: bool = True

    # Base de datos
    database_url: str = "postgresql+psycopg://europio:europio@localhost:5432/europio"

    # WhatsApp Cloud API
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_api_version: str = "v21.0"
    whatsapp_app_secret: str = ""  # para verificar la firma del webhook (X-Hub-Signature-256)

    # Seguridad del panel admin
    admin_api_key: str = ""  # clave requerida en el header X-API-Key para /admin

    @property
    def whatsapp_api_url(self) -> str:
        return (
            f"https://graph.facebook.com/{self.whatsapp_api_version}"
            f"/{self.whatsapp_phone_number_id}/messages"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
