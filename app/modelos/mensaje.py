from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class Mensaje(Base):
    __tablename__ = "mensajes"

    id = Column(Integer, primary_key=True)
    telefono = Column(String(20), nullable=False, index=True)
    direccion = Column(String(10), nullable=False)  # "entrante" (usuario) | "saliente" (bot)
    texto = Column(Text)
    creado_en = Column(DateTime(timezone=True), default=_ahora)
