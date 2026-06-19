"""Crea un usuario (asesor) para el panel del equipo.

Uso:
    python scripts/crear_usuario.py                          # pregunta todo
    python scripts/crear_usuario.py correo@x.com "Nombre"    # pide solo la contraseña

La contraseña se pide oculta (no queda en el historial de la terminal).
"""

import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal  # noqa: E402
from app.core.seguridad import hash_password  # noqa: E402
from app.modelos.usuario import Usuario  # noqa: E402


def main() -> None:
    email = (sys.argv[1] if len(sys.argv) > 1 else input("Correo: ")).strip().lower()
    nombre = (sys.argv[2] if len(sys.argv) > 2 else input("Nombre: ")).strip()
    password = getpass.getpass("Contraseña: ")
    if not (email and nombre and password):
        print("Faltan datos (correo, nombre y contraseña son obligatorios).")
        return

    db = SessionLocal()
    try:
        if db.query(Usuario).filter(Usuario.email == email).first():
            print(f"Ya existe un usuario con el correo {email}.")
            return
        usuario = Usuario(email=email, nombre=nombre, password_hash=hash_password(password))
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        print(f"✓ Usuario creado: {usuario.email} (id {usuario.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
