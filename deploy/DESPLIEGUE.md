# Despliegue en VPS Ubuntu (con dominio + HTTPS)

Guía para dejar el bot accesible en `https://TU_DOMINIO`, listo para el webhook de WhatsApp.
Reemplaza `TU_DOMINIO` y los valores entre `<...>` por los tuyos.

Requisitos: un VPS Ubuntu 22.04/24.04 con acceso SSH y `sudo`, y un dominio cuyo DNS puedas editar.

---

## 0. DNS (hazlo primero, tarda en propagar)

En el panel DNS de tu dominio crea un registro **A**:

```
Tipo: A    Nombre: bot (o @)    Valor: <IP_PUBLICA_DEL_VPS>
```

Verifica desde tu PC: `ping TU_DOMINIO` debe responder con la IP del VPS.

---

## 1. Preparar el servidor

```bash
ssh <usuario>@<IP_DEL_VPS>

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip postgresql nginx \
                    certbot python3-certbot-nginx git ufw

# Firewall
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'      # abre 80 y 443
sudo ufw --force enable
```

## 2. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE USER europio WITH PASSWORD '<CONTRASENA_BD>';
CREATE DATABASE europio OWNER europio;
SQL
```

## 3. Código de la app

```bash
# Usuario de sistema sin login, dueño de la app
sudo adduser --system --group europio

# Trae el código a /opt/europio (git clone si está en un remoto, o scp/rsync desde tu PC)
sudo git clone <URL_DEL_REPO> /opt/europio
#   alternativa sin git remoto, desde tu PC:
#   rsync -av --exclude .venv --exclude .git ./ <usuario>@<IP>:/tmp/europio/ && sudo mv /tmp/europio /opt/europio

sudo chown -R europio:europio /opt/europio

# Entorno virtual + dependencias
sudo -u europio python3 -m venv /opt/europio/.venv
sudo -u europio /opt/europio/.venv/bin/pip install -U pip
sudo -u europio /opt/europio/.venv/bin/pip install -r /opt/europio/requirements.txt
```

## 4. Variables de entorno (`.env` de producción)

```bash
sudo -u europio tee /opt/europio/.env >/dev/null <<'ENV'
APP_NAME=europio
ENVIRONMENT=production
DEBUG=false

DATABASE_URL=postgresql+psycopg://europio:<CONTRASENA_BD>@localhost:5432/europio

WHATSAPP_TOKEN=<TOKEN_DE_WHATSAPP>
WHATSAPP_PHONE_NUMBER_ID=1152487541284072
WHATSAPP_VERIFY_TOKEN=europio-webhook-2026
WHATSAPP_API_VERSION=v21.0
ENV

sudo chmod 600 /opt/europio/.env   # el .env tiene secretos
```

> El `WHATSAPP_TOKEN` temporal dura 24 h. Para producción genera un **token permanente**
> (System User) — ver sección al final.

## 5. Migraciones de la base de datos (Alembic)

Crea las tablas en la base recién creada:

```bash
sudo -u europio bash -c 'cd /opt/europio && .venv/bin/alembic upgrade head'
```

> Tras cada actualización de código que cambie modelos, vuelve a correr este comando
> (las nuevas revisiones de `alembic/versions/` se aplican con `alembic upgrade head`).

## 6. Servicio systemd (uvicorn)

```bash
sudo cp /opt/europio/deploy/europio.service /etc/systemd/system/europio.service
sudo systemctl daemon-reload
sudo systemctl enable --now europio

sudo systemctl status europio          # debe estar "active (running)"
curl -s http://127.0.0.1:8053/health   # {"status":"ok","app":"europio"}
```

Logs: `sudo journalctl -u europio -f`

## 7. nginx (reverse proxy)

```bash
sudo cp /opt/europio/deploy/nginx-europio.conf /etc/nginx/sites-available/europio
sudo sed -i 's/TU_DOMINIO/bot.tudominio.com/' /etc/nginx/sites-available/europio   # pon tu dominio
sudo ln -s /etc/nginx/sites-available/europio /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t && sudo systemctl reload nginx
```

## 8. HTTPS con Let's Encrypt

```bash
sudo certbot --nginx -d TU_DOMINIO     # añade el bloque 443 y el redirect; renovación automática
```

Prueba final desde tu PC:

```bash
curl https://TU_DOMINIO/health         # {"status":"ok","app":"europio"}
```

Si responde por HTTPS, el servidor está listo para el webhook. ✅

---

## 9. Webhook en Meta (siguiente paso)

En Meta → tu app → **WhatsApp → Configuration / Webhooks**:

- **Callback URL**: `https://TU_DOMINIO/webhook`
- **Verify token**: el mismo `WHATSAPP_VERIFY_TOKEN` del `.env` (`europio-webhook-2026`)
- Tras verificar, **suscríbete al campo `messages`**.

Meta hará un `GET /webhook` para verificar; el bot responde el `hub.challenge` automáticamente.

## 10. Token permanente (producción)

El token de 24 h caduca. Para uno que no expire:

1. Meta → **Business Settings → Users → System Users → Add** (rol Admin).
2. Asigna la app y genera token con permisos `whatsapp_business_messaging` y
   `whatsapp_business_management`.
3. Reemplaza `WHATSAPP_TOKEN` en `/opt/europio/.env` y `sudo systemctl restart europio`.

---

## Actualizar la app más adelante

```bash
cd /opt/europio
sudo -u europio git pull
sudo -u europio .venv/bin/pip install -r requirements.txt
sudo -u europio .venv/bin/alembic upgrade head   # aplica migraciones nuevas
sudo systemctl restart europio
```
