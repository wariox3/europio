from sqlalchemy import Column, Integer, String, Text

from app.core.db import Base


class Faq(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True)
    tema = Column(String(50), nullable=False)     # "registro", "colilla", "contrasena"
    pregunta_corta = Column(String(150))          # texto de la fila del menú
    respuesta = Column(Text, nullable=False)
    # Ruta o URL de una imagen que se envía tras la respuesta. NULL = sin imagen.
    # Si es relativa (p. ej. "/static/faqs/x.png") se antepone settings.public_base_url.
    imagen_url = Column(Text, nullable=True)
