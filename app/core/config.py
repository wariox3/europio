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
    whatsapp_app_id: str = ""      # App ID (no secreto); usado por el diagnóstico (debug_token)

    # Seguridad del panel admin
    admin_api_key: str = ""  # clave requerida en el header X-API-Key para /admin

    # Panel del equipo (sesión)
    session_secret: str = ""  # clave para firmar las cookies de sesión del panel

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
