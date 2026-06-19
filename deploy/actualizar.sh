#!/usr/bin/env bash
# Actualiza el bot europio: trae código, instala dependencias, migra, sincroniza FAQs y reinicia.
# Ejecutar como root o con sudo (necesario para systemctl).
set -euo pipefail

APP_DIR=/opt/europio
APP_USER=europio
SERVICIO=europio
HEALTH_URL=https://europio.uk/health

echo "==> Actualizando europio..."

# 1. Código
echo "==> git pull"
sudo -u "$APP_USER" git -C "$APP_DIR" pull

# 2. Dependencias
echo "==> Instalando dependencias"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q --no-cache-dir -r "$APP_DIR/requirements.txt"

# 3. Migraciones de base de datos
echo "==> Migraciones (alembic upgrade head)"
sudo -u "$APP_USER" bash -c "cd '$APP_DIR' && .venv/bin/alembic upgrade head"

# 3b. FAQs fijas (fixture)
echo "==> Sincronizando FAQs (cargar_faqs.py)"
sudo -u "$APP_USER" bash -c "cd '$APP_DIR' && .venv/bin/python scripts/cargar_faqs.py"

# 4. Reinicio del servicio
echo "==> Reiniciando servicio $SERVICIO"
systemctl daemon-reload
systemctl restart "$SERVICIO"

# 5. Verificación (la app tarda unos segundos en quedar lista; reintenta hasta 20s)
echo "==> Estado del servicio: $(systemctl is-active "$SERVICIO")"
echo "==> Health check:"
for i in $(seq 1 10); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "OK"
    break
  fi
  sleep 2
  [ "$i" -eq 10 ] && { echo "❌ Health check falló tras 20s"; exit 1; }
done

echo "==> ✅ Actualización completada."
