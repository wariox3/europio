import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.servicios.flujo import procesar_mensaje

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])


def _firma_valida(cuerpo: bytes, firma: str | None) -> bool:
    """Verifica la firma HMAC-SHA256 que envía Meta en X-Hub-Signature-256."""
    secret = settings.whatsapp_app_secret
    if not secret:
        # Sin app secret configurado no se puede verificar; se permite pero se avisa.
        logger.warning("WHATSAPP_APP_SECRET no configurado; se omite la verificación de firma.")
        return True
    if not firma or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(secret.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma.split("=", 1)[1])


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


def _extraer_mensaje(payload: dict) -> tuple[str, str, str] | None:
    """Extrae (telefono, texto, wamid) del payload de WhatsApp.

    `wamid` es el id único del mensaje (para deduplicar reintentos).
    Devuelve None para eventos que no son mensajes (p. ej. estados de entrega).
    """
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        mensajes = value.get("messages")
        if not mensajes:
            return None
        msg = mensajes[0]
        telefono = msg["from"]
        wamid = msg.get("id", "")
        tipo = msg.get("type")
        if tipo == "text":
            return telefono, msg["text"]["body"], wamid
        if tipo == "interactive":
            inter = msg["interactive"]
            reply = inter.get(inter.get("type"), {})  # list_reply | button_reply
            return telefono, reply.get("id", ""), wamid
        return telefono, "", wamid
    except (KeyError, IndexError, TypeError):
        return None


@router.post("/webhook")
async def recibir_webhook(request: Request, db: Session = Depends(get_db)) -> Response:
    cuerpo = await request.body()
    if not _firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
        logger.warning("Webhook con firma inválida; descartado.")
        return Response(status_code=403)

    try:
        payload = json.loads(cuerpo)
    except json.JSONDecodeError:
        return Response(status_code=400)

    extraido = _extraer_mensaje(payload)
    if extraido:
        telefono, texto, wamid = extraido
        try:
            await procesar_mensaje(telefono, texto, db, wamid=wamid)
        except Exception:
            # No propagamos: si devolvemos error, WhatsApp reintentaría la entrega.
            logger.exception("Error procesando mensaje de %s", telefono)
    # WhatsApp espera siempre 200 para no reintentar la entrega.
    return Response(content='{"status":"ok"}', media_type="application/json")
