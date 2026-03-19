FROM python:3.11-slim

LABEL maintainer="FoodViseur"
LABEL description="Self-hosted nutrition tracker PWA"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY static/ ./static/
COPY start.sh /app/start.sh

RUN mkdir -p /data && \
    chmod +x /app/start.sh && \
    chmod -R 755 /app

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/api/goals/ || exit 1

CMD ["sh", "/app/start.sh"]
