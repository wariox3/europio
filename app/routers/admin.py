import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.seguridad import ROLES, hash_password
from app.modelos.empresa import Empresa
from app.modelos.faq import Faq
from app.modelos.usuario import Usuario


def verificar_api_key(x_api_key: str = Header(default="")) -> None:
    """Exige el header X-API-Key con la clave de ADMIN_API_KEY."""
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="Admin deshabilitado: falta configurar ADMIN_API_KEY")
    if not secrets.compare_digest(x_api_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="API key inválida o ausente")


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verificar_api_key)])


class EmpresaIn(BaseModel):
    nombre: str
    alias: str = ""
    soporte: bool = True
    gestion_humana_nombre: str = ""
    gestion_humana_celular: str = ""


class EmpresaUpdate(BaseModel):
    nombre: str | None = None
    alias: str | None = None
    soporte: bool | None = None
    gestion_humana_nombre: str | None = None
    gestion_humana_celular: str | None = None


class FaqIn(BaseModel):
    tema: str
    pregunta_corta: str
    respuesta: str


class FaqUpdate(BaseModel):
    tema: str | None = None
    pregunta_corta: str | None = None
    respuesta: str | None = None


class UsuarioIn(BaseModel):
    email: str
    nombre: str
    password: str
    rol: str = "asesor"


class UsuarioUpdate(BaseModel):
    nombre: str | None = None
    rol: str | None = None
    activo: bool | None = None
    password: str | None = None


@router.post("/empresas")
def crear_empresa(datos: EmpresaIn, db: Session = Depends(get_db)) -> dict:
    empresa = Empresa(
        nombre=datos.nombre,
        alias=datos.alias,
        soporte=datos.soporte,
        gestion_humana_nombre=datos.gestion_humana_nombre,
        gestion_humana_celular=datos.gestion_humana_celular,
    )
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return {"id": empresa.id}


@router.get("/empresas")
def listar_empresas(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": e.id, "nombre": e.nombre, "alias": e.alias,
            "soporte": e.soporte,
            "gestion_humana_nombre": e.gestion_humana_nombre,
            "gestion_humana_celular": e.gestion_humana_celular,
        }
        for e in db.query(Empresa).order_by(Empresa.id).all()
    ]


@router.patch("/empresas/{empresa_id}")
def actualizar_empresa(empresa_id: int, datos: EmpresaUpdate, db: Session = Depends(get_db)) -> dict:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if datos.nombre is not None:
        empresa.nombre = datos.nombre
    if datos.alias is not None:
        empresa.alias = datos.alias
    if datos.soporte is not None:
        empresa.soporte = datos.soporte
    if datos.gestion_humana_nombre is not None:
        empresa.gestion_humana_nombre = datos.gestion_humana_nombre
    if datos.gestion_humana_celular is not None:
        empresa.gestion_humana_celular = datos.gestion_humana_celular
    db.commit()
    return {
        "id": empresa.id, "nombre": empresa.nombre, "alias": empresa.alias,
        "soporte": empresa.soporte,
        "gestion_humana_nombre": empresa.gestion_humana_nombre,
        "gestion_humana_celular": empresa.gestion_humana_celular,
    }


@router.post("/faqs")
def crear_faq(datos: FaqIn, db: Session = Depends(get_db)) -> dict:
    faq = Faq(tema=datos.tema, pregunta_corta=datos.pregunta_corta, respuesta=datos.respuesta)
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return {"id": faq.id}


@router.get("/faqs")
def listar_faqs(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": f.id, "tema": f.tema, "pregunta_corta": f.pregunta_corta, "respuesta": f.respuesta}
        for f in db.query(Faq).order_by(Faq.id).all()
    ]


@router.patch("/faqs/{faq_id}")
def actualizar_faq(faq_id: int, datos: FaqUpdate, db: Session = Depends(get_db)) -> dict:
    faq = db.get(Faq, faq_id)
    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")
    if datos.tema is not None:
        faq.tema = datos.tema
    if datos.pregunta_corta is not None:
        faq.pregunta_corta = datos.pregunta_corta
    if datos.respuesta is not None:
        faq.respuesta = datos.respuesta
    db.commit()
    return {"id": faq.id, "tema": faq.tema, "pregunta_corta": faq.pregunta_corta, "respuesta": faq.respuesta}


# --- Usuarios y roles ---------------------------------------------------------
# Estos endpoints están protegidos por X-API-Key (credencial de superadmin):
# solo quien tiene la clave puede crear/gestionar usuarios.

def _usuario_dict(u: Usuario) -> dict:
    return {"id": u.id, "email": u.email, "nombre": u.nombre, "rol": u.rol, "activo": u.activo}


@router.get("/roles")
def listar_roles() -> dict:
    """Roles disponibles para asignar a un usuario."""
    return {"roles": list(ROLES)}


@router.post("/usuarios")
def crear_usuario(datos: UsuarioIn, db: Session = Depends(get_db)) -> dict:
    if datos.rol not in ROLES:
        raise HTTPException(status_code=422, detail=f"Rol inválido. Use uno de: {', '.join(ROLES)}")
    email = datos.email.strip().lower()
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo")
    usuario = Usuario(
        email=email,
        nombre=datos.nombre.strip(),
        password_hash=hash_password(datos.password),
        rol=datos.rol,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return _usuario_dict(usuario)


@router.get("/usuarios")
def listar_usuarios(db: Session = Depends(get_db)) -> list[dict]:
    return [_usuario_dict(u) for u in db.query(Usuario).order_by(Usuario.id).all()]


@router.patch("/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: int, datos: UsuarioUpdate, db: Session = Depends(get_db)) -> dict:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if datos.rol is not None:
        if datos.rol not in ROLES:
            raise HTTPException(status_code=422, detail=f"Rol inválido. Use uno de: {', '.join(ROLES)}")
        usuario.rol = datos.rol
    if datos.nombre is not None:
        usuario.nombre = datos.nombre.strip()
    if datos.activo is not None:
        usuario.activo = datos.activo
    if datos.password is not None:
        usuario.password_hash = hash_password(datos.password)
    db.commit()
    return _usuario_dict(usuario)
