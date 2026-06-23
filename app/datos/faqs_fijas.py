"""FAQs fijas del bot (fuente de verdad única).

Estas preguntas frecuentes son siempre las mismas: este archivo es la fuente
de verdad. Para cambiarlas, edita la lista `FAQS_FIJAS` y vuelve a sembrarlas
con `scripts/cargar_faqs.py` (o `chat_local.py seed`).

Marcadores soportados en `respuesta` (ver `flujo.aplicar_plantilla`):
  {empresa}                  -> nombre de la empresa
  {gestion_humana_celular}   -> WhatsApp de Gestión Humana de la empresa

El orden de la lista es el orden en que aparecen en el menú.
"""

from sqlalchemy.orm import Session

from app.modelos.faq import Faq

FAQS_FIJAS: list[dict[str, str]] = [
    {
        "tema": "registro",
        "pregunta_corta": "Cómo registrarme",
        "respuesta": (
            'Ingresa a (https://www.empleado.co), busca el botón '
            '"Iniciar sesión" y debajo encontrarás el enlace "Regístrate". Allí '
            "deberás diligenciar tus datos.\n\n"
            "⚠️ Importante: el correo con el que te registres debe ser el mismo que "
            "tienes registrado en Gestión Humana de {empresa}. Si no estás seguro de "
            "cuál es, puedes verificarlo llamando o escribiendo al WhatsApp {gestion_humana_celular}.\n\n"
            "Después de registrarte, llegará un correíto con un link mágico ✨ para "
            "confirmar que el correo es tuyo y no de tu vecino. Dale unos minutitos, "
            "que el cartero digital no es tan rápido como WhatsApp."
        ),
        "imagen_url": "/static/faqs/1-registro.png",
    },
    {
        "tema": "verificar",
        "pregunta_corta": "Verificar cuenta",
        "respuesta": (
            "Si el correo de verificación no te llegó, primero revisa en tu bandeja "
            "de notificaciones o de no deseados/spam 📬: a veces el correo se pone "
            "loquito y se esconde ahí 🙈.\n\n"
            "Si definitivamente no aparece, ingresa a "
            '[www.empleado.co](https://www.empleado.co), busca el botón "Iniciar '
            'sesión" 🔐, entra con tu correo y clave, y si todo sale bien te aparecerá '
            "una opción para reenviar la verificación ✉️🔁."
        ),
        "imagen_url": "/static/faqs/2-verificacion.png",
    },
    {
        "tema": "asociar_empresa",
        "pregunta_corta": "Asociar empresa",
        "respuesta": (
            "¡Ya sabemos que tú eres el dueño de la cuenta! 😉 Ahora vamos a asociarla "
            "con tu información en la empresa.\n\n"
            'En la parte superior verás un mensaje que dice "Tu cuenta no está asociada '
            'a ninguna empresa" junto a un botón "Asociar empresa" 🏢. Dale clic y elige '
            "la empresa donde laboras 👆\n\n"
            "⚠️ Importante: El correo con el que te registraste y tu número de "
            "identificación deben coincidir exactamente con los datos que tiene "
            "{empresa} sobre ti. Si no coinciden, no podrás asociarte 🙅‍♂️\n\n"
            "¿Y si no te deja? Tranquilo, comunícate con {empresa} al 📱 {gestion_humana_celular} para "
            "verificar tus datos y vuelve a intentarlo 🔄"
        ),
        "imagen_url": "/static/faqs/3-enlazar-empresa.png",
    },
]


def sembrar_faqs(db: Session, *, podar: bool = True) -> dict[str, int]:
    """Sincroniza la tabla `faqs` con `FAQS_FIJAS` (idempotente).

    - Inserta los temas que falten y actualiza los existentes (clave: `tema`).
    - Si `podar` es True, elimina de la BD los temas que ya no estén en el fixture,
      dejando la tabla exactamente igual al fixture.

    Devuelve un resumen con cuántas FAQs se crearon, actualizaron y eliminaron.
    """
    existentes = {f.tema: f for f in db.query(Faq).all()}
    temas_fixture = {item["tema"] for item in FAQS_FIJAS}
    creadas = actualizadas = eliminadas = 0

    for item in FAQS_FIJAS:
        faq = existentes.get(item["tema"])
        if faq is None:
            db.add(Faq(**item))
            creadas += 1
        elif (faq.pregunta_corta, faq.respuesta, faq.imagen_url) != (
            item["pregunta_corta"], item["respuesta"], item.get("imagen_url"),
        ):
            faq.pregunta_corta = item["pregunta_corta"]
            faq.respuesta = item["respuesta"]
            faq.imagen_url = item.get("imagen_url")
            actualizadas += 1

    if podar:
        for tema, faq in existentes.items():
            if tema not in temas_fixture:
                db.delete(faq)
                eliminadas += 1

    db.commit()
    return {"creadas": creadas, "actualizadas": actualizadas, "eliminadas": eliminadas}
