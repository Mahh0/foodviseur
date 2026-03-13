FROM python:3.11-slim

LABEL maintainer="FoodViseur"
LABEL description="Self-hosted nutrition tracker PWA"

# Install system deps + gosu pour le drop de privilèges
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY static/ ./static/
COPY start.sh /app/start.sh

# /app appartient à root, lecture seule pour l'utilisateur final
# /data sera chown au runtime par start.sh
RUN mkdir -p /data && chmod +x /app/start.sh

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/goals/ || exit 1

# Le conteneur démarre en root — start.sh drop les privilèges via su-exec
CMD ["sh", "/app/start.sh"]
