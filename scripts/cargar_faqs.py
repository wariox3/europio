"""Carga (o sincroniza) las FAQs fijas en la base de datos del `.env`.

Las FAQs son siempre las mismas y viven en `app/datos/faqs_fijas.py`.
Este script deja la tabla `faqs` exactamente igual a ese fixture.

Uso:
    python scripts/cargar_faqs.py            # sincroniza (crea/actualiza/elimina sobrantes)
    python scripts/cargar_faqs.py --no-podar # no elimina temas que no estén en el fixture
"""

import os
import sys

# Permite ejecutar el script desde la raíz del proyecto (añade el root al path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal  # noqa: E402
from app.datos.faqs_fijas import sembrar_faqs  # noqa: E402


def main() -> None:
    podar = "--no-podar" not in sys.argv[1:]
    db = SessionLocal()
    try:
        resumen = sembrar_faqs(db, podar=podar)
    finally:
        db.close()
    print(
        "✓ FAQs sincronizadas: "
        f"{resumen['creadas']} creadas, "
        f"{resumen['actualizadas']} actualizadas, "
        f"{resumen['eliminadas']} eliminadas."
    )


if __name__ == "__main__":
    main()
