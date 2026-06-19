import logging
import os
from datetime import datetime, timedelta, timezone

# Colombia no tiene horario de verano: offset fijo UTC-5.
ZONA_LOCAL = timezone(timedelta(hours=-5))

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.seguridad import usuario_actual, verificar_password
from app.modelos.conversacion import Conversacion
from app.modelos.empresa import Empresa
from app.modelos.escalamiento import Escalamiento
from app.modelos.mensaje import Mensaje
from app.modelos.usuario import Usuario
from app.servicios.flujo import registrar_mensaje
from app.servicios.whatsapp import enviar_imagen, enviar_mensaje

logger = logging.getLogger(__name__)

_PLANTILLAS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plantillas")
templates = Jinja2Templates(directory=_PLANTILLAS)

router = APIRouter(prefix="/panel", tags=["panel"])


# --- helpers ------------------------------------------------------------------

def _lista_conversaciones(db: Session, filtro: str | None = None) -> list[dict]:
    """Conversaciones para el panel izquierdo, ordenadas por último mensaje.

    filtro="espera" -> solo las que esperan atención de un asesor (con_asesor).
    """
    consulta = db.query(Conversacion)
    if filtro == "espera":
        consulta = consulta.filter(Conversacion.estado == "con_asesor")
    items = []
    for c in consulta.all():
        ultimo = (
            db.query(Mensaje)
            .filter(Mensaje.telefono == c.telefono)
            .order_by(Mensaje.id.desc())
            .first()
        )
        empresa = db.get(Empresa, c.empresa_id) if c.empresa_id else None
        items.append({
            "telefono": c.telefono,
            "empresa": empresa.nombre if empresa else None,
            "ultimo": (
                ultimo.texto if ultimo and ultimo.texto
                else "📷 Imagen" if ultimo and ultimo.imagen_url
                else ""
            ),
            "orden": ultimo.id if ultimo else 0,
            "con_asesor": c.estado == "con_asesor",
            "no_leidos": c.no_leidos or 0,
        })
    # Primero las que esperan asesor; dentro de cada grupo, las de actividad más reciente.
    items.sort(key=lambda x: (x["con_asesor"], x["orden"]), reverse=True)
    return items


def _a_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite guarda naive; asume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZONA_LOCAL)


def _etiqueta_fecha(fecha) -> str:
    hoy = datetime.now(ZONA_LOCAL).date()
    if fecha == hoy:
        return "Hoy"
    if fecha == hoy - timedelta(days=1):
        return "Ayer"
    return fecha.strftime("%d/%m/%Y")


def _mensajes_render(db: Session, telefono: str) -> list[dict]:
    msgs = db.query(Mensaje).filter(Mensaje.telefono == telefono).order_by(Mensaje.id).all()
    nombres = {u.id: u.nombre for u in db.query(Usuario).all()}
    mensajes = []
    fecha_prev = None
    for m in msgs:
        local = _a_local(m.creado_en)
        fecha = local.date() if local else None
        mensajes.append({
            "direccion": m.direccion,
            "texto": m.texto,
            "imagen_url": m.imagen_url,
            "autor": (nombres.get(m.usuario_id) or "Asesor") if m.usuario_id else "Bot",
            "hora": local.strftime("%H:%M") if local else "",
            "sep": _etiqueta_fecha(fecha) if (fecha and fecha != fecha_prev) else None,
        })
        if fecha:
            fecha_prev = fecha
    return mensajes


def _marcar_leida(db: Session, telefono: str) -> Conversacion | None:
    conv = db.query(Conversacion).filter(Conversacion.telefono == telefono).first()
    if conv is not None and conv.no_leidos:
        conv.no_leidos = 0
        db.commit()
    return conv


def _contexto_chat(request: Request, db: Session, telefono: str, error: str | None = None) -> dict:
    conv = _marcar_leida(db, telefono)  # abrir la conversación la marca como leída
    empresa = db.get(Empresa, conv.empresa_id) if conv and conv.empresa_id else None
    return {
        "request": request,
        "telefono": telefono,
        "conv": conv,
        "mensajes": _mensajes_render(db, telefono),
        "empresa": empresa.nombre if empresa else None,
        "error": error,
    }


# --- autenticación ------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == email.strip().lower()).first()
    if usuario is None or not usuario.activo or not verificar_password(password, usuario.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Correo o contraseña inválidos."},
            status_code=401,
        )
    request.session["usuario_id"] = usuario.id
    return RedirectResponse("/panel", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/panel/login", status_code=303)


# --- vista tipo WhatsApp Web --------------------------------------------------

@router.get("", response_class=HTMLResponse)
def chats(
    request: Request,
    chat: str | None = None,
    filtro: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    ctx = {
        "request": request,
        "usuario": usuario,
        "items": _lista_conversaciones(db, filtro),
        "filtro": filtro,
        "chat": False,
    }
    if chat:
        ctx.update(_contexto_chat(request, db, chat))
        ctx["chat"] = True
    return templates.TemplateResponse("chat.html", ctx)


@router.get("/lista", response_class=HTMLResponse)
def fragmento_lista(
    request: Request,
    filtro: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    return templates.TemplateResponse(
        "_lista.html", {"request": request, "items": _lista_conversaciones(db, filtro)}
    )


@router.get("/chat/{telefono}", response_class=HTMLResponse)
def fragmento_chat(
    telefono: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    return templates.TemplateResponse("_chat_panel.html", _contexto_chat(request, db, telefono))


@router.get("/mensajes/{telefono}", response_class=HTMLResponse)
def fragmento_mensajes(
    telefono: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    # Refresco en vivo del hilo. Mientras está abierto, se mantiene como leído.
    _marcar_leida(db, telefono)
    return templates.TemplateResponse(
        "_mensajes.html", {"request": request, "mensajes": _mensajes_render(db, telefono)}
    )


@router.post("/conversaciones/{telefono}/responder")
async def responder(
    telefono: str,
    request: Request,
    texto: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    error = None
    texto = texto.strip()
    if texto:
        try:
            await enviar_mensaje(telefono, texto)
            registrar_mensaje(db, telefono, "saliente", texto, usuario_id=usuario.id)
        except Exception:
            logger.exception("Error enviando respuesta del asesor a %s", telefono)
            error = "envio"
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("_chat_panel.html", _contexto_chat(request, db, telefono, error))
    destino = f"/panel?chat={telefono}" + ("&error=envio" if error else "")
    return RedirectResponse(destino, status_code=303)


@router.post("/conversaciones/{telefono}/responder_imagen")
async def responder_imagen(
    telefono: str,
    request: Request,
    imagen_url: str = Form(...),
    caption: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    error = None
    imagen_url = imagen_url.strip()
    caption = caption.strip()
    if imagen_url:
        try:
            await enviar_imagen(telefono, imagen_url, caption or None)
            registrar_mensaje(
                db, telefono, "saliente", caption or None,
                usuario_id=usuario.id, imagen_url=imagen_url,
            )
        except Exception:
            logger.exception("Error enviando imagen del asesor a %s", telefono)
            error = "envio"
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("_chat_panel.html", _contexto_chat(request, db, telefono, error))
    destino = f"/panel?chat={telefono}" + ("&error=envio" if error else "")
    return RedirectResponse(destino, status_code=303)


@router.post("/conversaciones/{telefono}/eliminar")
def eliminar(
    telefono: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    db.query(Mensaje).filter(Mensaje.telefono == telefono).delete()
    db.query(Escalamiento).filter(Escalamiento.telefono == telefono).delete()
    db.query(Conversacion).filter(Conversacion.telefono == telefono).delete()
    db.commit()
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": "/panel"})
    return RedirectResponse("/panel", status_code=303)


@router.post("/conversaciones/{telefono}/cerrar")
def cerrar(
    telefono: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    conv = db.query(Conversacion).filter(Conversacion.telefono == telefono).first()
    if conv is not None:
        conv.estado = "finalizada"
        conv.cerrada_en = datetime.now(timezone.utc)
        conv.opciones = None
    db.query(Escalamiento).filter(
        Escalamiento.telefono == telefono, Escalamiento.atendido.is_(False)
    ).update({"atendido": True})
    db.commit()
    # Recarga completa para refrescar la lista de la izquierda.
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": f"/panel?chat={telefono}"})
    return RedirectResponse("/panel", status_code=303)
