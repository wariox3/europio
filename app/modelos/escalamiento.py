from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.core.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class Escalamiento(Base):
    __tablename__ = "escalamientos"

    id = Column(Integer, primary_key=True)
    telefono = Column(String(20))
    empresa_nombre = Column(String(150), nullable=True)  # se guarda el texto, no FK obligatorio
    motivo = Column(String(50))
    texto_original = Column(Text)
    atendido = Column(Boolean, default=False)
    creado_en = Column(DateTime(timezone=True), default=_ahora)
