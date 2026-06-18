import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modelos.conversacion import Conversacion
from app.modelos.empresa import Empresa
from app.modelos.escalamiento import Escalamiento
from app.modelos.faq import Faq
from app.modelos.mensaje import Mensaje
from app.servicios.resolver_empresa import resolver_empresa
from app.servicios.whatsapp import enviar_mensaje

logger = logging.getLogger(__name__)

MAX_OPCIONES = 9  # mantiene el menú corto y los números en un solo dígito
INACTIVIDAD = timedelta(hours=12)  # tras este tiempo, el siguiente mensaje reinicia
RESPUESTAS_NO = {"2", "no", "no gracias", "no, gracias", "salir", "nada", "ninguna"}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _esta_inactiva(conv: Conversacion) -> bool:
    ult = conv.actualizado_en
    if ult is None:
        return False
    if ult.tzinfo is None:  # SQLite guarda naive; asume UTC
        ult = ult.replace(tzinfo=timezone.utc)
    return (_ahora() - ult) > INACTIVIDAD


# --- historial de mensajes ----------------------------------------------------

def registrar_mensaje(db: Session, telefono: str, direccion: str, texto: str, wamid: str | None = None) -> None:
    db.add(Mensaje(telefono=telefono, direccion=direccion, texto=texto, wamid=wamid or None))
    db.commit()


async def _responder(db: Session, telefono: str, texto: str) -> None:
    """Registra el mensaje saliente en el historial y lo envía por WhatsApp."""
    registrar_mensaje(db, telefono, "saliente", texto)
    await enviar_mensaje(telefono, texto)


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

    Marcadores soportados: {empresa} (nombre) y {celular} (WhatsApp/teléfono).
    """
    if empresa is None:
        return texto
    return (
        texto
        .replace("{empresa}", empresa.nombre or "")
        .replace("{celular}", empresa.celular or "")
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
        + "\n\nResponde con el *número*, o escribe el nombre completo."
    )
    await _responder(db, telefono, cuerpo)
    return [e.id for e in empresas]


# --- transiciones reutilizables -----------------------------------------------

async def _ir_a_menu(conv: Conversacion, telefono: str, db: Session, empresa_id: int) -> None:
    conv.empresa_id = empresa_id
    conv.estado = "menu_principal"
    ids = await enviar_menu_principal(telefono, db)
    _guardar_opciones(conv, ids)
    db.commit()


# --- máquina de estados -------------------------------------------------------

async def procesar_mensaje(telefono: str, texto: str | None, db: Session, wamid: str | None = None) -> None:
    conv = obtener_o_crear_conversacion(db, telefono)

    # texto None => mensaje no de texto (audio, video, imagen, ubicación...).
    es_no_texto = texto is None
    texto_registro = "[mensaje no de texto]" if es_no_texto else texto

    # Registra el entrante. Si el wamid ya existe (reintento de WhatsApp), se descarta.
    try:
        registrar_mensaje(db, telefono, "entrante", texto_registro, wamid)
    except IntegrityError:
        db.rollback()
        logger.info("Mensaje duplicado (wamid=%s) descartado.", wamid)
        return

    # Si no es texto, pide texto y no altera el estado de la conversación.
    if es_no_texto:
        await _responder(
            db,
            telefono,
            "Por ahora solo puedo leer mensajes de texto 🙏. Por favor escríbeme "
            "tu consulta en un mensaje escrito.",
        )
        return

    # Reinicia si la conversación ya terminó o quedó inactiva mucho tiempo.
    if conv.estado == "finalizada" or _esta_inactiva(conv):
        conv.estado = "inicio"
        conv.empresa_id = None
        conv.opciones = None

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
            crear_escalamiento(db, telefono, None, "empresa_no_identificada", texto)
            await _responder(
                db,
                telefono,
                "Mmm, no logré identificar tu empresa. 😕 No te preocupes: le paso "
                "tu caso a una persona del equipo para que te contacte pronto.",
            )
        return

    if conv.estado == "menu_principal":
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
            await _responder(db, telefono, "¿Te puedo ayudar con algo más?\n\n1. Sí\n2. No")
        else:
            crear_escalamiento(db, telefono, conv.empresa_id, "intencion_no_reconocida", texto)
            await _responder(
                db,
                telefono,
                "Esa no la tengo a mano. 🤔 Te conecto con una persona del equipo "
                "para que te ayude; en un momento te contactan.",
            )
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
