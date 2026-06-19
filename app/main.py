import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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

    @app.get("/", response_class=HTMLResponse, tags=["inicio"])
    async def inicio() -> str:
        return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{settings.app_name}</title>
  <style>
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }}
    .tarjeta {{
      text-align: center;
      padding: 2.5rem 3rem;
      background: #1e293b;
      border-radius: 16px;
      box-shadow: 0 10px 40px rgba(0,0,0,.35);
    }}
    h1 {{ margin: 0 0 .5rem; font-size: 1.6rem; }}
    p {{ margin: .25rem 0 1.5rem; color: #94a3b8; }}
    .enlaces a {{
      display: inline-block;
      margin: .25rem .4rem;
      padding: .6rem 1.2rem;
      border-radius: 8px;
      text-decoration: none;
      background: #2563eb;
      color: #fff;
      font-weight: 600;
    }}
    .enlaces a.secundario {{ background: #334155; }}
    .estado {{ margin-top: 1.5rem; font-size: .85rem; color: #64748b; }}
  </style>
</head>
<body>
  <div class="tarjeta">
    <h1>{settings.app_name}</h1>
    <p>Bot de atención por WhatsApp</p>
    <div class="enlaces">
      <a href="/panel/login">Panel de soporte</a>
      <a class="secundario" href="/docs">API</a>
    </div>
    <div class="estado">Servicio activo · entorno: {settings.environment}</div>
  </div>
</body>
</html>"""

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
