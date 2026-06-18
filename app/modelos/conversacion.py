from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.core.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class Conversacion(Base):
    __tablename__ = "conversaciones"

    id = Column(Integer, primary_key=True)
    telefono = Column(String(20), nullable=False, unique=True, index=True)
    empresa_id = Column(Integer, nullable=True)
    estado = Column(String(30), default="inicio")
    # IDs (separados por coma) de las opciones del último menú numerado mostrado,
    # para mapear la respuesta numérica del usuario a la opción correcta.
    opciones = Column(String(255), nullable=True)
    # intentos consecutivos de identificar la empresa (para escalar tras N fallos)
    intentos = Column(Integer, default=0)
    creado_en = Column(DateTime(timezone=True), default=_ahora)
    actualizado_en = Column(DateTime(timezone=True), default=_ahora, onupdate=_ahora)
    cerrada_en = Column(DateTime(timezone=True), nullable=True)  # cuándo se finalizó
