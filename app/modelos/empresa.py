from sqlalchemy import Boolean, Column, Integer, String, text

from app.core.db import Base


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    alias = Column(String(500))  # variantes separadas por coma, refuerzan el fuzzy match
    # ¿La empresa tiene un plan de soporte activo con Semántica?
    soporte = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    # Datos de contacto de Gestión Humana, para empresas sin soporte.
    gestion_humana_nombre = Column(String(150))
    gestion_humana_celular = Column(String(30))
