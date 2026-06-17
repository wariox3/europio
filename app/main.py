from fastapi import FastAPI

from app.core.config import settings
from app.routers import admin, webhook


def create_app() -> FastAPI:
    # El esquema de la BD se gestiona con Alembic (`alembic upgrade head`).
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    app.include_router(webhook.router)
    app.include_router(admin.router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
