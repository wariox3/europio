import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.servicios.flujo import procesar_mensaje

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])


@router.get("/webhook")
async def verificar_webhook(request: Request) -> Response:
    """Verificación del webhook que exige WhatsApp Cloud API al configurarlo."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


def _extraer_mensaje(payload: dict) -> tuple[str, str] | None:
    """Extrae (telefono, texto) del payload de WhatsApp.

    Para respuestas de listas/botones devuelve el `id` de la opción elegida.
    Devuelve None para eventos que no son mensajes (p. ej. estados de entrega).
    """
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        mensajes = value.get("messages")
        if not mensajes:
            return None
        msg = mensajes[0]
        telefono = msg["from"]
        tipo = msg.get("type")
        if tipo == "text":
            return telefono, msg["text"]["body"]
        if tipo == "interactive":
            inter = msg["interactive"]
            reply = inter.get(inter.get("type"), {})  # list_reply | button_reply
            return telefono, reply.get("id", "")
        return telefono, ""
    except (KeyError, IndexError, TypeError):
        return None


@router.post("/webhook")
async def recibir_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.json()
    extraido = _extraer_mensaje(payload)
    if extraido:
        telefono, texto = extraido
        try:
            await procesar_mensaje(telefono, texto, db)
        except Exception:
            # No propagamos: si devolvemos error, WhatsApp reintentaría la entrega.
            logger.exception("Error procesando mensaje de %s", telefono)
    # WhatsApp espera siempre 200 para no reintentar la entrega.
    return {"status": "ok"}
