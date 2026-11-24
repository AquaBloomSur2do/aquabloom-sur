# 1. Usar una imagen oficial y ligera de Python
FROM python:3.11-slim

# 2. Instalar dependencia nativa requerida por rasterio
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Crear usuario y grupo del sistema sin privilegios
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# 4. Establecer el directorio de trabajo y ruta de paquetes del monorepo
WORKDIR /app
ENV PYTHONPATH=/app

# 5. Instalar dependencias primero (aprovecha la caché de capas de Docker)
COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

# 6. Copiar el código fuente requerido ajustando los permisos
COPY --chown=appuser:appgroup apps/api/app ./apps/api/app
COPY --chown=appuser:appgroup apps/satellite/app ./apps/satellite/app
COPY --chown=appuser:appgroup apps/scientific/app ./apps/scientific/app

# 7. Exponer el puerto en el que corre FastAPI
EXPOSE 8000

# 8. Restringir la ejecución al usuario sin privilegios
USER appuser

# 9. Comando para iniciar la aplicación con Uvicorn
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]


