from sqlalchemy import Column, Integer, String

from app.core.db import Base


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    alias = Column(String(500))  # variantes separadas por coma, refuerzan el fuzzy match
    celular = Column(String(30))  # WhatsApp/teléfono de Gestión Humana de la empresa
