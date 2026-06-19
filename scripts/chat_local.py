"""Simulador de conversación local del bot (sin WhatsApp).

Escribes como si fueras el usuario y ves lo que respondería el bot. Usa la misma
lógica (`app.servicios.flujo`) y tu base de datos local (la del `.env`).

Uso:
    python scripts/chat_local.py          # chat interactivo con los datos actuales
    python scripts/chat_local.py seed     # primero carga datos de ejemplo, luego chatea

El bot usa menús numerados: responde con el número de la opción (1, 2, 3...),
igual que lo hará el guarda en WhatsApp. Escribe `salir` para terminar.
"""

import asyncio
import os
import sys

# Permite ejecutar el script desde la raíz del proyecto (añade el root al path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.servicios.whatsapp as wa  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.datos.faqs_fijas import sembrar_faqs  # noqa: E402
from app.modelos.conversacion import Conversacion  # noqa: E402
from app.modelos.empresa import Empresa  # noqa: E402
from app.modelos.faq import Faq  # noqa: E402
from app.servicios.flujo import procesar_mensaje  # noqa: E402

TELEFONO_PRUEBA = "570000000000"


async def _imprimir_envio(payload: dict) -> None:
    """Reemplaza el envío real a WhatsApp: imprime el mensaje en consola."""
    tipo = payload.get("type")
    if tipo == "text":
        print(f"\n🤖 Bot: {payload['text']['body']}\n")
    elif tipo == "interactive":
        inter = payload["interactive"]
        print(f"\n🤖 Bot: {inter['body']['text']}")
        for fila in inter["action"]["sections"][0]["rows"]:
            print(f"     • [{fila['id']}] {fila['title']}")
        print("   (escribe el id entre corchetes para elegir)\n")
    else:
        print(f"\n🤖 Bot (payload): {payload}\n")


def sembrar_datos(db) -> None:
    if db.query(Empresa).count() == 0:
        db.add(Empresa(nombre="Comercializadora El Sol SAS", alias="el sol, elsol"))
        db.commit()
    # Las FAQs son fijas: se sincronizan desde el fixture (fuente de verdad única).
    sembrar_faqs(db)
    print("✓ Datos de ejemplo cargados (FAQs sincronizadas desde el fixture).\n")


async def main() -> None:
    # Sustituye el envío real por la impresión en consola.
    wa._post = _imprimir_envio

    db = SessionLocal()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "seed":
            sembrar_datos(db)

        # Reinicia el estado del teléfono de prueba para empezar limpio cada vez.
        db.query(Conversacion).filter(Conversacion.telefono == TELEFONO_PRUEBA).delete()
        db.commit()

        if db.query(Faq).count() == 0:
            print("⚠ No hay FAQs cargadas: el menú saldrá vacío.")
            print("  Corre con 'seed' para datos de ejemplo, o carga vía /admin.\n")

        print(f"Conversación local (teléfono simulado: {TELEFONO_PRUEBA}).")
        print("Escribe tus mensajes. 'salir' para terminar.\n")
        print("👉 Manda cualquier cosa para iniciar (ej: 'hola')")

        while True:
            try:
                texto = input("🙂 Tú: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if texto.lower() in ("salir", "exit", "quit"):
                break
            if not texto:
                continue
            await procesar_mensaje(TELEFONO_PRUEBA, texto, db)
    finally:
        db.close()
    print("\nFin de la conversación.")


if __name__ == "__main__":
    asyncio.run(main())
