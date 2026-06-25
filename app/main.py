import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.seguridad import NoAutenticado
from app.routers import admin, panel, usuarios, webhook
from app.servicios.flujo import cerrar_conversaciones_inactivas

logger = logging.getLogger(__name__)

# Cada cuánto se revisan las conversaciones para cerrarlas por inactividad.
INTERVALO_CIERRE_INACTIVAS = 15 * 60  # segundos


async def _bucle_cierre_inactivas() -> None:
    """Tarea de fondo: cierra periódicamente las conversaciones del bot inactivas."""
    while True:
        try:
            db = SessionLocal()
            try:
                await cerrar_conversaciones_inactivas(db)
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error en el cierre automático de conversaciones inactivas.")
        await asyncio.sleep(INTERVALO_CIERRE_INACTIVAS)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    tarea = asyncio.create_task(_bucle_cierre_inactivas())
    try:
        yield
    finally:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass


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

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=_lifespan)

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

    # Archivos estáticos públicos (p. ej. imágenes de las FAQs que envía el bot).
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="static",
    )

    app.include_router(webhook.router)
    app.include_router(admin.router)
    app.include_router(panel.router)
    app.include_router(usuarios.router)

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

    @app.get("/privacidad", response_class=HTMLResponse, tags=["legal"])
    async def privacidad() -> str:
        # Política de privacidad pública requerida por Meta para publicar la app.
        # AJUSTA: nombre de la empresa y correo de contacto (marcados abajo).
        empresa = "Semántica Digital"
        correo = "contacto@semanticadigital.com"  # AJUSTA este correo
        return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Política de Privacidad · {settings.app_name}</title>
  <style>
    body {{
      margin: 0;
      padding: 2.5rem 1rem;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      line-height: 1.6;
    }}
    main {{
      max-width: 760px;
      margin: 0 auto;
      background: #1e293b;
      border-radius: 16px;
      padding: 2.5rem;
      box-shadow: 0 10px 40px rgba(0,0,0,.35);
    }}
    h1 {{ font-size: 1.6rem; margin-top: 0; }}
    h2 {{ font-size: 1.15rem; margin-top: 2rem; color: #93c5fd; }}
    a {{ color: #93c5fd; }}
    .fecha {{ color: #64748b; font-size: .85rem; }}
  </style>
</head>
<body>
  <main>
    <h1>Política de Privacidad</h1>
    <p class="fecha">Última actualización: 22 de junio de 2026</p>

    <p>Esta política describe cómo <strong>{empresa}</strong> ("nosotros") trata
    la información de las personas que se comunican con nuestro servicio de
    atención al cliente a través de WhatsApp.</p>

    <h2>1. Qué datos recogemos</h2>
    <p>Cuando nos escribes por WhatsApp, recogemos únicamente:</p>
    <ul>
      <li>Tu número de teléfono de WhatsApp.</li>
      <li>El contenido de los mensajes que nos envías (texto e imágenes).</li>
      <li>La empresa que indicas para darle contexto a tu consulta.</li>
    </ul>

    <h2>2. Para qué los usamos</h2>
    <p>Usamos estos datos exclusivamente para atender tu consulta, responderte de
    forma automática o derivar la conversación a un asesor humano cuando sea
    necesario. No los usamos con fines publicitarios.</p>

    <h2>3. Con quién los compartimos</h2>
    <p>No vendemos ni cedemos tus datos a terceros. La mensajería se procesa a
    través de la plataforma WhatsApp Business de Meta, sujeta a sus propias
    condiciones.</p>

    <h2>4. Cuánto tiempo los conservamos</h2>
    <p>Conservamos el historial de la conversación el tiempo necesario para
    prestarte el servicio de soporte y cumplir obligaciones legales. Puedes
    solicitar su eliminación escribiéndonos.</p>

    <h2>5. Tus derechos</h2>
    <p>Puedes solicitar acceder, rectificar o eliminar tus datos en cualquier
    momento escribiendo a <a href="mailto:{correo}">{correo}</a>.</p>

    <h2>6. Contacto</h2>
    <p>Para cualquier duda sobre esta política, escríbenos a
    <a href="mailto:{correo}">{correo}</a>.</p>
  </main>
</body>
</html>"""

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
