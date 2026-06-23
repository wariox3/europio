import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modelos.conversacion import Conversacion
from app.modelos.empresa import Empresa
from app.modelos.escalamiento import Escalamiento
from app.modelos.faq import Faq
from app.modelos.mensaje import Mensaje
from app.core.config import settings
from app.servicios.resolver_empresa import resolver_empresa
from app.servicios.whatsapp import enviar_imagen, enviar_mensaje

logger = logging.getLogger(__name__)

MAX_OPCIONES = 9  # mantiene el menú corto y los números en un solo dígito
INACTIVIDAD = timedelta(hours=1)  # tras este tiempo, el siguiente mensaje reinicia
AUTO_CIERRE_ASESOR = timedelta(hours=24)  # auto-cierre de seguridad si nadie atiende
MAX_INTENTOS_EMPRESA = 3  # intentos de identificar empresa antes de escalar
RESPUESTAS_NO = {"2", "no", "no gracias", "no, gracias", "salir", "nada", "ninguna"}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _inactiva(conv: Conversacion, limite: timedelta) -> bool:
    ult = conv.actualizado_en
    if ult is None:
        return False
    if ult.tzinfo is None:  # SQLite guarda naive; asume UTC
        ult = ult.replace(tzinfo=timezone.utc)
    return (_ahora() - ult) > limite


# --- historial de mensajes ----------------------------------------------------

def registrar_mensaje(
    db: Session,
    telefono: str,
    direccion: str,
    texto: str | None,
    wamid: str | None = None,
    usuario_id: int | None = None,
    imagen_url: str | None = None,
) -> None:
    db.add(Mensaje(
        telefono=telefono,
        direccion=direccion,
        texto=texto,
        wamid=wamid or None,
        usuario_id=usuario_id,
        imagen_url=imagen_url,
    ))
    db.commit()


async def _responder(db: Session, telefono: str, texto: str) -> None:
    """Registra el mensaje saliente en el historial y lo envía por WhatsApp."""
    registrar_mensaje(db, telefono, "saliente", texto)
    await enviar_mensaje(telefono, texto)


def _url_publica(ruta: str) -> str:
    """Convierte una ruta relativa (/static/...) en URL absoluta pública.

    Si ya es absoluta (http...) la devuelve tal cual.
    """
    if ruta.startswith(("http://", "https://")):
        return ruta
    return f"{settings.public_base_url.rstrip('/')}{ruta}"


async def _responder_imagen(
    db: Session, telefono: str, imagen_url: str, caption: str | None = None
) -> None:
    """Envía una imagen del bot por WhatsApp y la registra en el historial."""
    url = _url_publica(imagen_url)
    registrar_mensaje(db, telefono, "saliente", caption, imagen_url=imagen_url)
    await enviar_imagen(telefono, url, caption)


# --- helpers de persistencia --------------------------------------------------

def obtener_o_crear_conversacion(db: Session, telefono: str) -> Conversacion:
    conv = (
        db.query(Conversacion)
        .filter(Conversacion.telefono == telefono)
        .order_by(Conversacion.id.desc())
        .first()
    )
    if conv is None:
        conv = Conversacion(telefono=telefono, estado="inicio")
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def crear_escalamiento(db: Session, telefono: str, empresa_id, motivo: str, texto: str) -> None:
    nombre = None
    if empresa_id:
        empresa = db.get(Empresa, empresa_id)
        nombre = empresa.nombre if empresa else None
    db.add(Escalamiento(
        telefono=telefono,
        empresa_nombre=nombre,
        motivo=motivo,
        texto_original=texto,
    ))
    db.commit()


# --- opciones del menú numerado ----------------------------------------------

def _guardar_opciones(conv: Conversacion, ids: list[int]) -> None:
    conv.opciones = ",".join(str(i) for i in ids) if ids else None


def _leer_opciones(conv: Conversacion) -> list[int]:
    if not conv.opciones:
        return []
    return [int(x) for x in conv.opciones.split(",") if x]


def _opcion_elegida(texto: str, ids: list[int]) -> int | None:
    """Si el texto es un número válido del menú, devuelve el id correspondiente."""
    t = texto.strip()
    if t.isdigit() and ids:
        n = int(t)
        if 1 <= n <= len(ids):
            return ids[n - 1]
    return None


def aplicar_plantilla(texto: str, empresa: Empresa | None) -> str:
    """Reemplaza los marcadores de la FAQ con los datos de la empresa.

    Marcadores soportados: {empresa} (nombre) y {empresa_celular} (WhatsApp/teléfono).
    """
    if empresa is None:
        return texto
    return (
        texto
        .replace("{empresa}", empresa.nombre or "")
        .replace("{empresa_celular}", empresa.celular or "")
    )


def buscar_faq_por_texto(db: Session, texto: str) -> Faq | None:
    """Coincidencia por texto libre (tema exacto o parte de la pregunta corta)."""
    t = texto.strip().lower()
    if not t:
        return None
    return (
        db.query(Faq)
        .filter((Faq.tema.ilike(t)) | (Faq.pregunta_corta.ilike(f"%{t}%")))
        .first()
    )


# --- construcción de menús (texto numerado) -----------------------------------

async def enviar_menu_principal(telefono: str, db: Session) -> list[int]:
    """Envía el menú de temas como texto numerado. Devuelve los ids en orden."""
    faqs = db.query(Faq).order_by(Faq.id).all()
    if not faqs:
        await _responder(
            db,
            telefono,
            "Por ahora no tengo temas disponibles para mostrarte. 🙌 Le aviso a "
            "una persona del equipo para que te ayude.",
        )
        return []
    lineas = [f"{i}. {faq.pregunta_corta or faq.tema}" for i, faq in enumerate(faqs, 1)]
    cuerpo = (
        "¡Genial! 🙌 ¿Sobre qué tema necesitas ayuda?\n\n"
        + "\n".join(lineas)
        + "\n0. Hablar con un asesor 🧑‍💼"
        + "\n\nResponde con el *número* de la opción."
    )
    await _responder(db, telefono, cuerpo)
    return [faq.id for faq in faqs]


async def enviar_opciones_empresas(telefono: str, candidatos_ids: list[int], db: Session) -> list[int]:
    """Envía las empresas candidatas como texto numerado. Devuelve los ids en orden."""
    empresas = [e for e in (db.get(Empresa, eid) for eid in candidatos_ids[:MAX_OPCIONES]) if e]
    lineas = [f"{i}. {e.nombre}" for i, e in enumerate(empresas, 1)]
    cuerpo = (
        "Encontré varias empresas parecidas. ¿Cuál es la tuya?\n\n"
        + "\n".join(lineas)
        + "\n0. No está en la lista"
        + "\n\nResponde con el *número*, o escribe el nombre completo."
    )
    await _responder(db, telefono, cuerpo)
    return [e.id for e in empresas]


# --- transiciones reutilizables -----------------------------------------------

def _mensaje_sin_soporte(empresa: Empresa) -> str:
    """Mensaje para empresas sin plan de soporte activo."""
    nombre = empresa.gestion_humana_nombre or "—"
    celular = empresa.gestion_humana_celular or "—"
    return (
        "❌ Tu empresa no cuenta con un plan de soporte activo con Semántica.\n"
        "Para este tipo de solicitudes, debes contactar directamente a tu "
        "departamento de Gestión Humana:\n"
        f"👤 {nombre}\n\n"
        f"📲 {celular} (WhatsApp)"
    )


async def _ir_a_menu(conv: Conversacion, telefono: str, db: Session, empresa_id: int) -> None:
    conv.empresa_id = empresa_id
    conv.estado = "menu_principal"
    conv.intentos = 0
    ids = await enviar_menu_principal(telefono, db)
    _guardar_opciones(conv, ids)
    db.commit()


async def _escalar_empresa(conv: Conversacion, telefono: str, db: Session, texto: str) -> None:
    """No se pudo identificar la empresa tras varios intentos: pasa a un asesor."""
    crear_escalamiento(db, telefono, None, "empresa_no_identificada", texto)
    conv.estado = "con_asesor"
    conv.intentos = 0
    conv.opciones = None
    conv.no_leidos = 0
    db.commit()
    await _responder(
        db,
        telefono,
        "No logré identificar tu empresa. 😕 No te preocupes: le paso "
        "tu caso a un asesor para que te contacte pronto.",
    )


# --- máquina de estados -------------------------------------------------------

async def procesar_mensaje(
    telefono: str,
    texto: str | None,
    db: Session,
    wamid: str | None = None,
    imagen_url: str | None = None,
) -> None:
    conv = obtener_o_crear_conversacion(db, telefono)

    # Sin texto => mensaje no procesable por el bot (audio, video, ubicación...).
    # Una imagen sin caption entra aquí, pero igual se guarda para mostrarla.
    es_no_texto = texto is None
    if texto is not None:
        texto_registro = texto
    elif imagen_url is not None:
        texto_registro = None  # imagen sola: el panel muestra la imagen
    else:
        texto_registro = "[mensaje no de texto]"

    # Registra el entrante. Si el wamid ya existe (reintento de WhatsApp), se descarta.
    try:
        registrar_mensaje(db, telefono, "entrante", texto_registro, wamid, imagen_url=imagen_url)
    except IntegrityError:
        db.rollback()
        logger.info("Mensaje duplicado (wamid=%s) descartado.", wamid)
        return

    # Conversación con un asesor: el bot está MUDO (lo atiende un humano).
    # Solo se libera por auto-cierre de seguridad si nadie respondió en mucho tiempo.
    if conv.estado == "con_asesor":
        if _inactiva(conv, AUTO_CIERRE_ASESOR):
            conv.estado = "inicio"
            conv.empresa_id = None
            conv.opciones = None
            conv.intentos = 0
            conv.no_leidos = 0
        else:
            # mudo: el mensaje queda registrado para el asesor y suma a no leídos.
            conv.no_leidos = (conv.no_leidos or 0) + 1
            db.commit()
            return

    # Si no es texto, no altera el estado de la conversación.
    if es_no_texto:
        if imagen_url is not None:
            # Imagen recibida (y guardada): el bot no puede interpretarla, pide texto.
            await _responder(
                db,
                telefono,
                "Recibí tu imagen 📷, pero para ayudarte por aquí necesito que me "
                "escribas tu consulta en *texto* 🙏.",
            )
        else:
            # Audio, video, documento, ubicación, sticker, etc.: no permitido.
            await _responder(
                db,
                telefono,
                "⚠️ Ese tipo de recurso no está permitido. Por ahora solo puedo "
                "recibir *texto* o *imágenes* 🙏.",
            )
        return

    # Reinicia si la conversación ya terminó o quedó inactiva mucho tiempo.
    if conv.estado == "finalizada" or _inactiva(conv, INACTIVIDAD):
        conv.estado = "inicio"
        conv.empresa_id = None
        conv.opciones = None
        conv.intentos = 0

    if conv.estado == "inicio":
        await _responder(
            db,
            telefono,
            "¡Hola! 👋 Te damos la bienvenida al canal de soporte del portal de "
            "empleados. Para empezar, cuéntame: ¿en qué empresa trabajas?",
        )
        conv.estado = "esperando_empresa"
        db.commit()
        return

    if conv.estado in ("esperando_empresa", "confirmando_empresa"):
        # En la lista de candidatas, "0" = "no está en la lista". Consume intento
        # (para no quedar en bucle) y, si se acaban, escala.
        if conv.estado == "confirmando_empresa" and texto.strip() == "0":
            conv.intentos = (conv.intentos or 0) + 1
            if conv.intentos >= MAX_INTENTOS_EMPRESA:
                await _escalar_empresa(conv, telefono, db, texto)
            else:
                conv.estado = "esperando_empresa"
                conv.opciones = None
                db.commit()
                restantes = MAX_INTENTOS_EMPRESA - conv.intentos
                await _responder(
                    db, telefono,
                    "De acuerdo 🙌 Escríbeme de nuevo el *nombre de tu empresa*. "
                    f"(Te {'queda' if restantes == 1 else 'quedan'} {restantes} "
                    f"intento{'' if restantes == 1 else 's'}.)",
                )
            return

        # ¿Eligió por número una de las empresas que le ofrecimos?
        empresa_id = _opcion_elegida(texto, _leer_opciones(conv))
        if empresa_id is not None:
            await _ir_a_menu(conv, telefono, db, empresa_id)
            return

        # Si no, intenta resolver por el nombre que escribió.
        empresas = db.query(Empresa).all()
        resultado = resolver_empresa(texto, empresas)
        if resultado["match"]:
            await _ir_a_menu(conv, telefono, db, resultado["match"])
        elif resultado["candidatos"]:
            conv.estado = "confirmando_empresa"
            ids = await enviar_opciones_empresas(telefono, resultado["candidatos"], db)
            _guardar_opciones(conv, ids)
            db.commit()
        else:
            # No se reconoció: cicla hasta MAX_INTENTOS_EMPRESA y luego escala.
            conv.intentos = (conv.intentos or 0) + 1
            if conv.intentos >= MAX_INTENTOS_EMPRESA:
                await _escalar_empresa(conv, telefono, db, texto)
            else:
                restantes = MAX_INTENTOS_EMPRESA - conv.intentos
                db.commit()
                await _responder(
                    db,
                    telefono,
                    "No encontré esa empresa 🤔. Por favor escribe el *nombre completo* "
                    f"de tu empresa. (Te {'queda' if restantes == 1 else 'quedan'} "
                    f"{restantes} intento{'' if restantes == 1 else 's'}.)",
                )
        return

    if conv.estado == "menu_principal":
        # Opción 0: hablar con un asesor humano.
        if texto.strip() == "0":
            empresa = db.get(Empresa, conv.empresa_id) if conv.empresa_id else None
            # Empresa sin plan de soporte: no se escala; se deriva a Gestión Humana.
            # El cliente sigue en el menú y puede seguir autogestionándose con las FAQs.
            if empresa is not None and not empresa.soporte:
                await _responder(db, telefono, _mensaje_sin_soporte(empresa))
                return
            crear_escalamiento(db, telefono, conv.empresa_id, "solicita_asesor", texto)
            conv.estado = "con_asesor"
            conv.opciones = None
            conv.no_leidos = 0
            db.commit()
            await _responder(
                db,
                telefono,
                "Con gusto 🙌 Le aviso a un asesor para que te contacte. "
                "En un momento se comunican contigo.",
            )
            return

        # Primero por número del menú; si no, por texto libre.
        faq = None
        faq_id = _opcion_elegida(texto, _leer_opciones(conv))
        if faq_id is not None:
            faq = db.get(Faq, faq_id)
        if faq is None:
            faq = buscar_faq_por_texto(db, texto)

        if faq:
            empresa = db.get(Empresa, conv.empresa_id) if conv.empresa_id else None
            await _responder(db, telefono, aplicar_plantilla(faq.respuesta, empresa))
            conv.estado = "preguntando_mas"
            db.commit()
            prompt = "¿Te puedo ayudar con algo más?\n\n1. Sí\n2. No"
            # Si la FAQ trae imagen, la pregunta va como caption de la imagen para
            # garantizar el orden (las imágenes por link de WhatsApp llegan con retraso).
            if faq.imagen_url:
                await _responder_imagen(db, telefono, faq.imagen_url, caption=prompt)
            else:
                await _responder(db, telefono, prompt)
        else:
            # No se reconoció: vuelve a mostrar el menú y cicla hasta una opción
            # válida (o el cierre por inactividad). No escala automáticamente.
            await _responder(
                db,
                telefono,
                "No entendí esa opción 🤔. Por favor responde con el *número* de una "
                "de estas (o *0* para hablar con un asesor):",
            )
            ids = await enviar_menu_principal(telefono, db)
            _guardar_opciones(conv, ids)
            db.commit()
        return

    if conv.estado == "preguntando_mas":
        if texto.strip().lower() in RESPUESTAS_NO:
            conv.estado = "finalizada"
            conv.cerrada_en = _ahora()
            conv.opciones = None
            db.commit()
            await _responder(
                db, telefono,
                "¡Gracias por escribirnos! 👋 Que tengas un buen día.",
            )
        else:
            # Cualquier otra cosa: vuelve a mostrar el menú de temas.
            conv.estado = "menu_principal"
            ids = await enviar_menu_principal(telefono, db)
            _guardar_opciones(conv, ids)
            db.commit()
        return
