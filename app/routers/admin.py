from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modelos.empresa import Empresa
from app.modelos.faq import Faq

router = APIRouter(prefix="/admin", tags=["admin"])


class EmpresaIn(BaseModel):
    nombre: str
    alias: str = ""
    celular: str = ""


class EmpresaUpdate(BaseModel):
    nombre: str | None = None
    alias: str | None = None
    celular: str | None = None


class FaqIn(BaseModel):
    tema: str
    pregunta_corta: str
    respuesta: str


class FaqUpdate(BaseModel):
    tema: str | None = None
    pregunta_corta: str | None = None
    respuesta: str | None = None


@router.post("/empresas")
def crear_empresa(datos: EmpresaIn, db: Session = Depends(get_db)) -> dict:
    empresa = Empresa(nombre=datos.nombre, alias=datos.alias, celular=datos.celular)
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return {"id": empresa.id}


@router.get("/empresas")
def listar_empresas(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": e.id, "nombre": e.nombre, "alias": e.alias, "celular": e.celular}
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
    if datos.celular is not None:
        empresa.celular = datos.celular
    db.commit()
    return {"id": empresa.id, "nombre": empresa.nombre, "alias": empresa.alias, "celular": empresa.celular}


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
