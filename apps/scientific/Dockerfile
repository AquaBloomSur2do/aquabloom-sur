FROM python:3.11-slim

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

ENV PYTHONPATH=/app \
    SCIENTIFIC_PORT=8003

COPY requirements.txt ./apps/scientific/requirements.txt
RUN pip install --no-cache-dir -r apps/scientific/requirements.txt

COPY --chown=appuser:appgroup app ./apps/scientific/app

EXPOSE 8003

USER appuser

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os; from urllib.request import urlopen; port = os.getenv('SCIENTIFIC_PORT', '8003'); response = urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=3); exit(0 if response.status == 200 else 1)"]

CMD ["uvicorn", "apps.scientific.app.main:app", "--host", "0.0.0.0", "--port", "8003"]


