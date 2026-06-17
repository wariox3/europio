# europio

Bot de soporte por WhatsApp — **proyecto 100% independiente**. Tiene su propia base
de datos y no consume ningún sistema externo (ni Flúor ni el ERP). La empresa solo
sirve para dar contexto a la conversación y para que el escalamiento a un humano
llegue con esa información.

## Arquitectura

```
WhatsApp Cloud API  →  Bot Soporte (FastAPI, standalone)
                              ↓
                         PostgreSQL: empresas, faqs, conversaciones, escalamientos
```

- **Sin Claude/LLM**: el flujo es 100% por reglas (menús interactivos + fuzzy match).
- **Sin clientes HTTP a otros sistemas**: todo vive en su propia BD.

## Estructura

```
app/
├── main.py                     # App, routers y creación de tablas (lifespan)
├── core/
│   ├── config.py               # Settings (BD + credenciales WhatsApp)
│   └── db.py                   # Engine, SessionLocal, Base, get_db
├── modelos/                    # SQLAlchemy: empresa, faq, conversacion, escalamiento
├── servicios/
│   ├── resolver_empresa.py     # Fuzzy match de empresa (rapidfuzz)
│   ├── whatsapp.py             # Envío de mensajes/listas (WhatsApp Cloud API)
│   └── flujo.py                # Máquina de estados de la conversación
└── routers/
    ├── webhook.py              # GET (verificación) + POST (mensajes entrantes)
    └── admin.py                # Alta/listado de empresas y FAQs
```

## Estados de la conversación

`inicio → esperando_empresa → (confirmando_empresa) → menu_principal`

1. **inicio**: saluda y pide el nombre de la empresa.
2. **esperando_empresa / confirmando_empresa**: resuelve la empresa por fuzzy match.
   Si hay match claro (≥85) avanza; si hay varios candidatos (≥60) ofrece una lista
   interactiva; si no, crea un escalamiento `empresa_no_identificada`.
3. **menu_principal**: muestra las FAQs como lista. La opción elegida responde con su
   texto. Si llega algo no reconocido, crea un escalamiento `intencion_no_reconocida`.

## Puesta en marcha

```bash
# 1. Entorno virtual
python3 -m venv .venv && source .venv/bin/activate

# 2. Dependencias
pip install -r requirements.txt

# 3. PostgreSQL (ejemplo con Docker)
docker run -d --name europio-db -p 5432:5432 \
  -e POSTGRES_USER=europio -e POSTGRES_PASSWORD=europio -e POSTGRES_DB=europio \
  postgres:16

# 4. Variables de entorno
cp .env.example .env   # ajusta DATABASE_URL y credenciales de WhatsApp

# 5. Crear/actualizar el esquema de la BD (migraciones Alembic)
alembic upgrade head

# 6. Arrancar
uvicorn app.main:app --reload
```

> El esquema de la BD se gestiona con **Alembic**. Tras cambiar un modelo:
> `alembic revision --autogenerate -m "..."` y luego `alembic upgrade head`.

## Configuración de WhatsApp Cloud API

En el panel de Meta, configura el webhook apuntando a `https://<tu-host>/webhook`:

- **Verify token**: el valor de `WHATSAPP_VERIFY_TOKEN` (Meta hace un `GET /webhook`
  para verificarlo).
- Los mensajes entrantes llegan como `POST /webhook`.

Sin `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` el bot funciona en **dry-run**: no
envía nada real, solo registra el payload en el log (útil para desarrollo local).

## Cargar empresas y FAQs

```bash
curl -X POST localhost:8000/admin/empresas \
  -H 'content-type: application/json' \
  -d '{"nombre":"Comercializadora El Sol SAS","alias":"el sol, elsol"}'

curl -X POST localhost:8000/admin/faqs \
  -H 'content-type: application/json' \
  -d '{"tema":"registro","pregunta_corta":"Cómo registrarme","respuesta":"Entra a portal.example.com y crea tu usuario."}'
```

- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
