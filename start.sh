#!/bin/sh
set -e

echo "Starting FoodViseur..."

# Migrations Alembic
echo "Running Alembic migrations..."
cd /app
alembic upgrade head

# Lancer uvicorn
echo "Starting uvicorn..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level ${LOG_LEVEL:-info}
