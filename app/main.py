import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.seguridad import NoAutenticado
from app.routers import admin, panel, webhook

logger = logging.getLogger(__name__)


def _init_sentry() -> None:
    """Inicializa Sentry si hay DSN configurado. Sin DSN no hace nada."""
    if not settings.sentry_dsn:
        logger.info("SENTRY_DSN no configurado; el monitoreo de errores está desactivado.")
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # No enviar datos personales (cuerpos de petición, cookies, etc.) por defecto.
        send_default_pii=False,
    )
    logger.info("Sentry inicializado (environment=%s).", settings.environment)


def create_app() -> FastAPI:
    # El esquema de la BD se gestiona con Alembic (`alembic upgrade head`).
    _init_sentry()

    app = FastAPI(title=settings.app_name, debug=settings.debug)

    secret = settings.session_secret
    if not secret:
        logger.warning(
            "SESSION_SECRET no configurado; uso una clave efímera (las sesiones "
            "del panel se pierden al reiniciar). Configúralo en producción."
        )
        secret = secrets.token_urlsafe(32)
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        https_only=(settings.environment == "production"),
        same_site="lax",
    )

    # Rutas del panel sin sesión -> redirige al login.
    @app.exception_handler(NoAutenticado)
    async def _redirigir_login(request: Request, exc: NoAutenticado) -> RedirectResponse:
        return RedirectResponse("/panel/login", status_code=303)

    app.include_router(webhook.router)
    app.include_router(admin.router)
    app.include_router(panel.router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
