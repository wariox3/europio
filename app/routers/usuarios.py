import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.seguridad import ROLES, hash_password, requiere_superadmin
from app.modelos.usuario import Usuario

_PLANTILLAS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plantillas")
templates = Jinja2Templates(directory=_PLANTILLAS)

# Todo el router exige rol superadmin (además de sesión válida).
router = APIRouter(prefix="/panel/usuarios", tags=["usuarios"])


def _form(request: Request, actual: Usuario, *, editado: Usuario | None = None, error: str | None = None,
          status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        "usuario_form.html",
        {"request": request, "usuario": actual, "editado": editado, "roles": ROLES, "error": error},
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse)
def listar_usuarios(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_superadmin),
) -> HTMLResponse:
    usuarios = db.query(Usuario).order_by(Usuario.id).all()
    return templates.TemplateResponse(
        "usuarios.html",
        {"request": request, "usuario": usuario, "usuarios": usuarios},
    )


@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_form(
    request: Request,
    usuario: Usuario = Depends(requiere_superadmin),
) -> HTMLResponse:
    return _form(request, usuario)


@router.post("/nuevo", response_class=HTMLResponse)
def crear_usuario(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    rol: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_superadmin),
):
    email = email.strip().lower()
    nombre = nombre.strip()
    if rol not in ROLES:
        return _form(request, usuario, error="Rol inválido.", status_code=422)
    if not (email and nombre and password):
        return _form(request, usuario, error="Nombre, correo y contraseña son obligatorios.", status_code=422)
    if db.query(Usuario).filter(Usuario.email == email).first():
        return _form(request, usuario, error="Ya existe un usuario con ese correo.", status_code=409)
    db.add(Usuario(email=email, nombre=nombre, rol=rol, password_hash=hash_password(password)))
    db.commit()
    return RedirectResponse("/panel/usuarios", status_code=303)


@router.get("/{usuario_id}/editar", response_class=HTMLResponse)
def editar_form(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_superadmin),
) -> HTMLResponse:
    editado = db.get(Usuario, usuario_id)
    if editado is None:
        return RedirectResponse("/panel/usuarios", status_code=303)
    return _form(request, usuario, editado=editado)


@router.post("/{usuario_id}/editar", response_class=HTMLResponse)
def actualizar_usuario(
    usuario_id: int,
    request: Request,
    nombre: str = Form(...),
    rol: str = Form(...),
    activo: bool = Form(False),
    password: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_superadmin),
):
    editado = db.get(Usuario, usuario_id)
    if editado is None:
        return RedirectResponse("/panel/usuarios", status_code=303)
    nombre = nombre.strip()
    if rol not in ROLES:
        return _form(request, usuario, editado=editado, error="Rol inválido.", status_code=422)
    if not nombre:
        return _form(request, usuario, editado=editado, error="El nombre es obligatorio.", status_code=422)
    # Un superadmin no puede quitarse su propio rol ni desactivarse (evita autobloqueo).
    if editado.id == usuario.id and (rol != usuario.rol or not activo):
        return _form(
            request, usuario, editado=editado,
            error="No puedes quitarte el rol de superadmin ni desactivar tu propia cuenta.",
            status_code=422,
        )
    editado.nombre = nombre
    editado.rol = rol
    editado.activo = activo
    if password.strip():
        editado.password_hash = hash_password(password)
    db.commit()
    return RedirectResponse("/panel/usuarios", status_code=303)
