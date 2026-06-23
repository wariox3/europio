"""Crea un usuario para el panel del equipo.

Uso:
    python scripts/crear_usuario.py                                   # pregunta todo
    python scripts/crear_usuario.py correo@x.com "Nombre"            # pide solo la contraseña
    python scripts/crear_usuario.py correo@x.com "Nombre" superadmin # asigna el rol

Útil para crear el primer superadmin. La contraseña se pide oculta.
Roles válidos: {roles}.
"""

import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal  # noqa: E402
from app.core.seguridad import ROL_ASESOR, ROLES, hash_password  # noqa: E402
from app.modelos.usuario import Usuario  # noqa: E402

__doc__ = __doc__.format(roles=", ".join(ROLES))


def main() -> None:
    email = (sys.argv[1] if len(sys.argv) > 1 else input("Correo: ")).strip().lower()
    nombre = (sys.argv[2] if len(sys.argv) > 2 else input("Nombre: ")).strip()
    rol = (sys.argv[3] if len(sys.argv) > 3 else input(f"Rol [{ROL_ASESOR}]: ") or ROL_ASESOR).strip()
    if rol not in ROLES:
        print(f"Rol inválido '{rol}'. Use uno de: {', '.join(ROLES)}.")
        return
    password = getpass.getpass("Contraseña: ")
    if not (email and nombre and password):
        print("Faltan datos (correo, nombre y contraseña son obligatorios).")
        return

    db = SessionLocal()
    try:
        if db.query(Usuario).filter(Usuario.email == email).first():
            print(f"Ya existe un usuario con el correo {email}.")
            return
        usuario = Usuario(
            email=email, nombre=nombre, password_hash=hash_password(password), rol=rol
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        print(f"✓ Usuario creado: {usuario.email} (rol {usuario.rol}, id {usuario.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
