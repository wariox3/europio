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
        resp.raise_for_status()


async def enviar_mensaje(telefono: str, texto: str) -> None:
    await _post({
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": texto},
    })


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
