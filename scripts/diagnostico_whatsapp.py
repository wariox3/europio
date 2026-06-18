"""Diagnóstico de la conexión con WhatsApp Cloud API.

Revisa el token configurado, su validez y permisos (vía debug_token) y,
opcionalmente, envía un mensaje de prueba a un número.

Uso:
    python scripts/diagnostico_whatsapp.py                  # revisa token y permisos
    python scripts/diagnostico_whatsapp.py 573001234567     # además envía un mensaje de prueba

Lee del .env: WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_APP_ID,
WHATSAPP_APP_SECRET. (El App ID y App Secret solo se usan para ver los permisos.)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402


def revisar_configuracion() -> str:
    token = settings.whatsapp_token
    print("== Configuración ==")
    print(f"  token presente : {bool(token)}  (longitud: {len(token)})")
    if token and token != token.strip():
        print("  ⚠️  el token tiene espacios o saltos de línea al inicio/fin")
    print(f"  phone_number_id: {settings.whatsapp_phone_number_id or '(vacío)'}")
    print(f"  app_id         : {settings.whatsapp_app_id or '(no configurado)'}")
    print(f"  app_secret     : {'sí' if settings.whatsapp_app_secret else 'no'}")
    return token


def revisar_permisos(token: str) -> None:
    print("\n== Validez y permisos (debug_token) ==")
    if not (settings.whatsapp_app_id and settings.whatsapp_app_secret):
        print("  (omitido: configura WHATSAPP_APP_ID y WHATSAPP_APP_SECRET para verlo)")
        return
    try:
        r = httpx.get(
            "https://graph.facebook.com/debug_token",
            params={
                "input_token": token,
                "access_token": f"{settings.whatsapp_app_id}|{settings.whatsapp_app_secret}",
            },
            timeout=15,
        )
    except httpx.HTTPError as e:
        print(f"  error de red: {e}")
        return
    data = r.json().get("data")
    if not data:
        print("  respuesta inesperada:", r.json())
        return
    print(f"  válido : {data.get('is_valid')}")
    print(f"  expira : {data.get('expires_at')}  (0 = nunca)")
    scopes = data.get("scopes") or []
    print(f"  scopes : {scopes}")
    if "whatsapp_business_messaging" not in scopes:
        print("  ❌ falta 'whatsapp_business_messaging' → regenera el token marcando ese permiso")
    else:
        print("  ✓ tiene whatsapp_business_messaging")


def enviar_prueba(token: str, numero: str) -> None:
    print(f"\n== Envío de prueba a {numero} ==")
    try:
        r = httpx.post(
            settings.whatsapp_api_url,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messaging_product": "whatsapp",
                "to": numero,
                "type": "text",
                "text": {"body": "Prueba de diagnóstico ✅"},
            },
            timeout=15,
        )
    except httpx.HTTPError as e:
        print(f"  error de red: {e}")
        return
    print(f"  status: {r.status_code}")
    print(f"  {r.text}")
    if r.status_code == 200:
        print("  ✓ enviado (revisa que llegue al WhatsApp del destinatario)")


def main() -> None:
    token = revisar_configuracion()
    if not token:
        print("\nNo hay token configurado (WHATSAPP_TOKEN vacío). El bot estaría en dry-run.")
        return
    revisar_permisos(token)
    if len(sys.argv) > 1:
        enviar_prueba(token, sys.argv[1].strip())
    else:
        print("\n(Para enviar un mensaje de prueba: python scripts/diagnostico_whatsapp.py <numero>)")


if __name__ == "__main__":
    main()
