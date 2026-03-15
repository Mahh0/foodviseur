#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "Starting FoodViseur with UID=${PUID} GID=${PGID}"

# Créer le groupe et l'utilisateur s'ils n'existent pas
if ! getent group appgroup > /dev/null 2>&1; then
    groupadd -g "${PGID}" appgroup
fi
if ! getent passwd appuser > /dev/null 2>&1; then
    useradd -u "${PUID}" -g appgroup -s /bin/sh -M -d /app appuser 2>/dev/null || true
fi

# Ajuster les permissions du volume /data
chown -R appuser:appgroup /data

# Migrations Alembic (en root depuis /app)
echo "Running Alembic migrations..."
cd /app
alembic upgrade head

# Chown la base après migration (alembic tourne en root)
chown -R appuser:appgroup /data

# Lancer uvicorn en tant qu'appuser
echo "Starting uvicorn..."
exec gosu appuser uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level ${LOG_LEVEL:-info}
