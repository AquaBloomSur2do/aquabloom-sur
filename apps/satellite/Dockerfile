FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

ENV PYTHONPATH=/app \
    SATELLITE_PORT=8002

COPY requirements.txt ./apps/satellite/requirements.txt
RUN pip install --no-cache-dir -r apps/satellite/requirements.txt

COPY --chown=appuser:appgroup app ./apps/satellite/app

EXPOSE 8002

USER appuser

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os; from urllib.request import urlopen; port = os.getenv('SATELLITE_PORT', '8002'); response = urlopen(f'http://127.0.0.1:{port}/health', timeout=3); exit(0 if response.status == 200 else 1)"]

CMD ["uvicorn", "apps.satellite.app.main:app", "--host", "0.0.0.0", "--port", "8002"]



