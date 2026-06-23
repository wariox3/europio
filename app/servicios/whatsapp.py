import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _post(payload: dict) -> None:
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        # Sin credenciales (desarrollo): no se envía nada real, solo se registra.
        logger.info("WhatsApp (dry-run) -> %s", payload)
        return
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(settings.whatsapp_api_url, json=payload, headers=headers)
        if resp.status_code >= 400:
            # Registra el detalle del error de la API de Meta (token inválido, etc.).
            logger.error("WhatsApp API %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()


async def enviar_mensaje(telefono: str, texto: str) -> None:
    await _post({
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": texto},
    })


async def enviar_imagen(telefono: str, url: str, caption: str | None = None) -> None:
    """Envía una imagen por su URL pública (HTTPS, JPEG/PNG, máx. 5 MB).

    El `caption` es texto opcional bajo la imagen (límite de WhatsApp: ~1024 chars).
    """
    imagen: dict[str, str] = {"link": url}
    if caption:
        imagen["caption"] = caption
    await _post({
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "image",
        "image": imagen,
    })


async def descargar_media(media_id: str) -> tuple[bytes, str] | None:
    """Descarga un archivo recibido por su `media_id` desde la API de WhatsApp.

    El flujo de Meta son dos pasos: primero se consulta el media_id para obtener
    una URL temporal, y luego se descarga esa URL (ambas con el token Bearer).

    Devuelve (contenido, mime_type) o None si no hay token o falla la descarga.
    """
    if not settings.whatsapp_token:
        logger.info("WhatsApp (dry-run): no se descarga media %s (sin token).", media_id)
        return None
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    base = f"https://graph.facebook.com/{settings.whatsapp_api_version}"
    async with httpx.AsyncClient(timeout=30) as client:
        meta = await client.get(f"{base}/{media_id}", headers=headers)
        if meta.status_code >= 400:
            logger.error("WhatsApp media meta %s: %s", meta.status_code, meta.text)
            return None
        info = meta.json()
        url = info.get("url")
        mime = info.get("mime_type", "application/octet-stream")
        if not url:
            return None
        archivo = await client.get(url, headers=headers)
        if archivo.status_code >= 400:
            logger.error("WhatsApp media descarga %s: %s", archivo.status_code, archivo.text)
            return None
        return archivo.content, mime


async def enviar_lista(telefono: str, cuerpo: str, boton: str, filas: list[dict]) -> None:
    """Envía un mensaje interactivo tipo lista.

    filas: [{"id": "...", "title": "..." (<=24 chars), "description": "..." (opcional)}]
    """
    await _post({
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": cuerpo},
            "action": {
                "button": boton,
                "sections": [{"title": "Opciones", "rows": filas}],
            },
        },
    })
