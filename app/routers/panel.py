import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
from app.servicios.whatsapp import enviar_mensaje

logger = logging.getLogger(__name__)

_PLANTILLAS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plantillas")
templates = Jinja2Templates(directory=_PLANTILLAS)

router = APIRouter(prefix="/panel", tags=["panel"])


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


# --- bandeja ------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
def bandeja(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    convs = (
        db.query(Conversacion)
        .filter(Conversacion.estado == "con_asesor")
        .order_by(Conversacion.actualizado_en)
        .all()
    )
    items = []
    for c in convs:
        esc = (
            db.query(Escalamiento)
            .filter(Escalamiento.telefono == c.telefono, Escalamiento.atendido.is_(False))
            .order_by(Escalamiento.id.desc())
            .first()
        )
        empresa = db.get(Empresa, c.empresa_id) if c.empresa_id else None
        nombre_empresa = empresa.nombre if empresa else (esc.empresa_nombre if esc else None)
        items.append({"conv": c, "empresa": nombre_empresa, "motivo": esc.motivo if esc else None})
    return templates.TemplateResponse(
        "bandeja.html", {"request": request, "usuario": usuario, "items": items}
    )


# --- conversación -------------------------------------------------------------

@router.get("/conversaciones/{telefono}", response_class=HTMLResponse)
def ver_conversacion(
    telefono: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    conv = db.query(Conversacion).filter(Conversacion.telefono == telefono).first()
    mensajes = db.query(Mensaje).filter(Mensaje.telefono == telefono).order_by(Mensaje.id).all()
    nombres = {u.id: u.nombre for u in db.query(Usuario).all()}
    empresa = db.get(Empresa, conv.empresa_id) if conv and conv.empresa_id else None
    return templates.TemplateResponse(
        "conversacion.html",
        {
            "request": request,
            "usuario": usuario,
            "telefono": telefono,
            "conv": conv,
            "mensajes": mensajes,
            "nombres": nombres,
            "empresa": empresa.nombre if empresa else None,
        },
    )


@router.post("/conversaciones/{telefono}/responder")
async def responder(
    telefono: str,
    texto: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_actual),
):
    texto = texto.strip()
    if texto:
        try:
            await enviar_mensaje(telefono, texto)
        except Exception:
            logger.exception("Error enviando respuesta del asesor a %s", telefono)
            return RedirectResponse(f"/panel/conversaciones/{telefono}?error=envio", status_code=303)
        registrar_mensaje(db, telefono, "saliente", texto, usuario_id=usuario.id)
    return RedirectResponse(f"/panel/conversaciones/{telefono}", status_code=303)


@router.post("/conversaciones/{telefono}/cerrar")
def cerrar(
    telefono: str,
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
    return RedirectResponse("/panel", status_code=303)
