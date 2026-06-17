from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modelos.empresa import Empresa
from app.modelos.faq import Faq

router = APIRouter(prefix="/admin", tags=["admin"])


class EmpresaIn(BaseModel):
    nombre: str
    alias: str = ""


class FaqIn(BaseModel):
    tema: str
    pregunta_corta: str
    respuesta: str


@router.post("/empresas")
def crear_empresa(datos: EmpresaIn, db: Session = Depends(get_db)) -> dict:
    empresa = Empresa(nombre=datos.nombre, alias=datos.alias)
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return {"id": empresa.id}


@router.get("/empresas")
def listar_empresas(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": e.id, "nombre": e.nombre, "alias": e.alias}
        for e in db.query(Empresa).order_by(Empresa.id).all()
    ]


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
