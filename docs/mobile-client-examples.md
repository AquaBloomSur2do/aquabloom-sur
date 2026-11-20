# Ejemplos de Consumo API para Cliente Móvil (AquaBloom Sur)

Esta guía proporciona ejemplos de consumo (`curl`) para que los desarrolladores de la aplicación móvil (React Native) puedan interactuar con la API Gateway de AquaBloom Sur.

## 1. Autenticación (Supabase)

La aplicación móvil debe autenticarse directamente contra Supabase Auth para obtener el JWT. La API de AquaBloom Sur no maneja el login directamente, sino que valida el token generado por Supabase.

*Requisito:* Incluir el token JWT en el encabezado `Authorization: Bearer <TOKEN>` en todas las peticiones a `/api/v1/*`.

## 2. Consulta Pública: Catálogo de Lagos

Permite a la aplicación móvil listar los lagos disponibles y su información general.

**Petición:**
```bash
curl -X GET "http://api.aquabloomsur.cl/api/v1/lakes?page=1&page_size=10" \
     -H "Authorization: Bearer <TU_JWT>" \
     -H "Accept: application/json"
```

**Respuesta Exitosa (200 OK):**
```json
{
  "items": [
    {
      "id": "a278bacc-735f-4089-ab55-0390a776c706",
      "name": "Lago Villarrica",
      "region": "Araucanía",
      "surface_area_km2": 173.0,
      "stations_count": 5
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

## 3. Seguimiento de Trabajos Científicos (Estimaciones)

Si el usuario móvil dispara o consulta una estimación de clorofila, debe sondear el estado del trabajo asíncrono.

**Petición de Estado:**
```bash
curl -X GET "http://api.aquabloomsur.cl/api/v1/executions/jobs/8f9d3b2a-1c4e-5f6a-7b8c-9d0e1f2a3b4c" \
     -H "Authorization: Bearer <TU_JWT>" \
     -H "Accept: application/json"
```

**Respuestas Posibles (Ejemplos):**
```json
[
  {
    "job_id": "8f9d3b2a-1c4e-5f6a-7b8c-9d0e1f2a3b4c",
    "job_type": "ESTIMATION",
    "status": "IN_PROGRESS",
    "message": "Calculando índice NDCI sobre la escena...",
    "created_at": "2026-10-29T14:30:00Z"
  },
  {
    "job_id": "8f9d3b2a-1c4e-5f6a-7b8c-9d0e1f2a3b4c",
    "job_type": "ESTIMATION",
    "status": "COMPLETED",
    "message": "Estimación finalizada correctamente.",
    "result_url": "/api/v1/estimations/products/a1b2c3d4",
    "completed_at": "2026-10-29T14:35:00Z"
  },
  {
    "job_id": "8f9d3b2a-1c4e-5f6a-7b8c-9d0e1f2a3b4c",
    "job_type": "ESTIMATION",
    "status": "FAILED",
    "error_message": "Error de calidad: exceso de cobertura nubosa en el polígono del lago.",
    "completed_at": "2026-10-29T14:31:15Z"
  }
]
```

## 4. Consulta de Estimación Final (Puntos de Muestra)

Una vez completado el trabajo, el cliente móvil puede consultar los resultados por punto (no mapa ráster).

**Petición:**
```bash
curl -X GET "http://api.aquabloomsur.cl/api/v1/estimations/products/a1b2c3d4" \
     -H "Authorization: Bearer <TU_JWT>" \
     -H "Accept: application/json"
```

**Respuesta Exitosa (200 OK):**
```json
{
  "product_id": "a1b2c3d4",
  "lake_id": "a278bacc-735f-4089-ab55-0390a776c706",
  "model_version_id": "m5n6o7p8",
  "target_variable": "chlorophyll_a",
  "unit": "ug/L",
  "points": [
    {
      "station_id": "ebbfd61d-a87d-4d1d-9d17-b19bfa574953",
      "station_name": "Centro Villarrica",
      "estimated_value": 3.45,
      "quality_flag": "VALID",
      "warnings": []
    },
    {
      "station_id": "f5e4d3c2-b1a0-9f8e-7d6c-5b4a3928170",
      "station_name": "Desembocadura Trancura",
      "estimated_value": 8.2,
      "quality_flag": "VALID",
      "warnings": ["Extrapolación detectada: valor fuera del rango de entrenamiento."]
    }
  ]
}
```