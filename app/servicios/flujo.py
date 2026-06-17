from sqlalchemy.orm import Session

from app.modelos.conversacion import Conversacion
from app.modelos.empresa import Empresa
from app.modelos.escalamiento import Escalamiento
from app.modelos.faq import Faq
from app.servicios.resolver_empresa import resolver_empresa
from app.servicios.whatsapp import enviar_lista, enviar_mensaje


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


def buscar_faq_por_opcion(db: Session, texto: str) -> Faq | None:
    # En el menú, la selección llega como "faq:<id>" (respuesta de lista interactiva).
    if texto.startswith("faq:"):
        try:
            faq_id = int(texto.split(":", 1)[1])
        except ValueError:
            return None
        return db.get(Faq, faq_id)
    # Texto libre: intenta casar por tema exacto o por pregunta_corta.
    t = texto.strip().lower()
    if not t:
        return None
    return (
        db.query(Faq)
        .filter((Faq.tema.ilike(t)) | (Faq.pregunta_corta.ilike(f"%{t}%")))
        .first()
    )


# --- construcción de menús ----------------------------------------------------

async def enviar_menu_principal(telefono: str, db: Session) -> None:
    filas = [
        {"id": f"faq:{faq.id}", "title": (faq.pregunta_corta or faq.tema)[:24]}
        for faq in db.query(Faq).order_by(Faq.id).all()
    ]
    if not filas:
        await enviar_mensaje(telefono, "Por ahora no hay temas disponibles. Te conecto con el equipo.")
        return
    await enviar_lista(telefono, "¿En qué te puedo ayudar?", "Ver temas", filas)


async def enviar_lista_empresas(telefono: str, candidatos_ids: list[int], db: Session) -> None:
    filas = []
    for empresa_id in candidatos_ids[:10]:  # WhatsApp permite máx. 10 filas por sección
        empresa = db.get(Empresa, empresa_id)
        if empresa:
            filas.append({"id": f"empresa:{empresa.id}", "title": empresa.nombre[:24]})
    await enviar_lista(telefono, "¿Cuál es tu empresa?", "Ver empresas", filas)


# --- máquina de estados -------------------------------------------------------

async def procesar_mensaje(telefono: str, texto: str, db: Session) -> None:
    conv = obtener_o_crear_conversacion(db, telefono)

    if conv.estado == "inicio":
        await enviar_mensaje(telefono, "¡Hola! ¿Cuál es el nombre de tu empresa?")
        conv.estado = "esperando_empresa"
        db.commit()
        return

    if conv.estado in ("esperando_empresa", "confirmando_empresa"):
        # Confirmación directa desde la lista interactiva.
        if texto.startswith("empresa:"):
            try:
                conv.empresa_id = int(texto.split(":", 1)[1])
            except ValueError:
                conv.empresa_id = None
            conv.estado = "menu_principal"
            db.commit()
            await enviar_menu_principal(telefono, db)
            return

        empresas = db.query(Empresa).all()
        resultado = resolver_empresa(texto, empresas)
        if resultado["match"]:
            conv.empresa_id = resultado["match"]
            conv.estado = "menu_principal"
            db.commit()
            await enviar_menu_principal(telefono, db)
        elif resultado["candidatos"]:
            conv.estado = "confirmando_empresa"
            db.commit()
            await enviar_lista_empresas(telefono, resultado["candidatos"], db)
        else:
            crear_escalamiento(db, telefono, None, "empresa_no_identificada", texto)
            await enviar_mensaje(telefono, "No logré identificar tu empresa, ya te vamos a contactar.")
        return

    if conv.estado == "menu_principal":
        faq = buscar_faq_por_opcion(db, texto)
        if faq:
            await enviar_mensaje(telefono, faq.respuesta)
        else:
            crear_escalamiento(db, telefono, conv.empresa_id, "intencion_no_reconocida", texto)
            await enviar_mensaje(telefono, "No tengo esa respuesta a mano, te conecto con alguien del equipo.")
        return
