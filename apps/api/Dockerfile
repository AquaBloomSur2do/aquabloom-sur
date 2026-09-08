# 1. Usar una imagen oficial y ligera de Python
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Instalar dependencias primero (aprovecha la caché de capas de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar el código fuente de la aplicación al contenedor
COPY app/ ./app/

# 5. Exponer el puerto en el que corre FastAPI
EXPOSE 8000

# 6. Comando para iniciar la aplicación con Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
