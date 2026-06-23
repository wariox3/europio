import hashlib
import hmac
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.servicios.flujo import procesar_mensaje
from app.servicios.whatsapp import descargar_media

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])

# Carpeta donde se guardan las imágenes entrantes (servidas en /static/media).
MEDIA_DIR = Path(__file__).resolve().parents[1] / "static" / "media"
_EXT_POR_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


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


def _extraer_mensaje(payload: dict) -> tuple[str, str | None, str, str | None] | None:
    """Extrae (telefono, texto, wamid, media_id) del payload de WhatsApp.

    `texto` es None cuando el mensaje no trae texto. En imágenes, `texto` es el
    caption (si lo hay) y `media_id` el id del archivo para descargarlo; en el
    resto de mensajes no de texto `media_id` es None.
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
            return telefono, msg["text"]["body"], wamid, None
        if tipo == "interactive":
            inter = msg["interactive"]
            reply = inter.get(inter.get("type"), {})  # list_reply | button_reply
            return telefono, reply.get("id", ""), wamid, None
        if tipo == "image":
            img = msg.get("image", {})
            return telefono, img.get("caption"), wamid, img.get("id")
        return telefono, None, wamid, None  # audio, video, ubicación, etc.
    except (KeyError, IndexError, TypeError):
        return None


async def _guardar_media(media_id: str) -> str | None:
    """Descarga la imagen entrante y la guarda en /static/media.

    Devuelve la ruta pública (p. ej. /static/media/123.jpg) o None si falla.
    """
    descarga = await descargar_media(media_id)
    if descarga is None:
        return None
    contenido, mime = descarga
    ext = _EXT_POR_MIME.get(mime, "bin")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    nombre = f"{media_id}.{ext}"
    (MEDIA_DIR / nombre).write_bytes(contenido)
    return f"/static/media/{nombre}"


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
        telefono, texto, wamid, media_id = extraido
        imagen_url = await _guardar_media(media_id) if media_id else None
        try:
            await procesar_mensaje(telefono, texto, db, wamid=wamid, imagen_url=imagen_url)
        except Exception:
            # No propagamos: si devolvemos error, WhatsApp reintentaría la entrega.
            logger.exception("Error procesando mensaje de %s", telefono)
    # WhatsApp espera siempre 200 para no reintentar la entrega.
    return Response(content='{"status":"ok"}', media_type="application/json")
