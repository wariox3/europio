from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, text

from app.core.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    email = Column(String(150), nullable=False, unique=True, index=True)
    nombre = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Rol del usuario. "superadmin" puede gestionar usuarios; el resto, no.
    rol = Column(String(30), nullable=False, default="asesor", server_default=text("'asesor'"))
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), default=_ahora)
