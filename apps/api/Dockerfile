# 1. Usar una imagen oficial y ligera de Python
FROM python:3.11-slim

# 2. Crear usuario y grupo del sistema sin privilegios
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# 3. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Instalar dependencias primero (aprovecha la caché de capas de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el código fuente ajustando los permisos al nuevo usuario
COPY --chown=appuser:appgroup app/ ./app/

# 6. Exponer el puerto en el que corre FastAPI
EXPOSE 8000

# 7. Restringir la ejecución al usuario sin privilegios
USER appuser

# 8. Comando para iniciar la aplicación con Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]