import bcrypt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modelos.usuario import Usuario


class NoAutenticado(Exception):
    """Se lanza cuando una ruta del panel requiere sesión y no la hay."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Dependencia: devuelve el usuario en sesión o lanza NoAutenticado."""
    uid = request.session.get("usuario_id")
    if not uid:
        raise NoAutenticado()
    usuario = db.get(Usuario, uid)
    if usuario is None or not usuario.activo:
        raise NoAutenticado()
    return usuario
