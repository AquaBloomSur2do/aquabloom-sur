# Definición del Caso Demostrable — Piloto Sprint 2 (AquaBloom Sur)

Este documento establece los límites científicos y técnicos para la ejecución del piloto experimental de extremo a extremo durante el Sprint 2, asegurando que el alcance sea viable dentro de la capacidad de 120 horas del equipo.

## 1. Selección de Entidades y Variables
Para aislar el experimento y validar la arquitectura de los microservicios sin sobrecargar el procesamiento, se define el siguiente caso único:
* **Lago objetivo:** Lago Panguipulli (SRID 4326).
* **Variable objetivo:** Clorofila-a ($Chl-a$), medida en $\mu g/L$.
* **Índice espectral:** NDCI (Normalized Difference Chlorophyll Index). Específico para la detección de floraciones algales.

## 2. Insumo Satelital (Satellite)
* **Fuente:** Un (1) recorte previamente preparado de una escena Sentinel-2 L2A (Nivel 2A, reflectancia de superficie).
* **Condiciones:** El archivo ya cuenta con sus bandas alineadas y recorte perimetral aplicado sobre el Lago Panguipulli. 
* **Límite:** Durante este sprint **no** se implementará la búsqueda, descarga on-the-fly ni el procesamiento automatizado directo desde el hub de Copernicus. El sistema consumirá este insumo estático previamente verificado.

## 3. Conjunto de Observaciones (Dataset)
* **Muestras in-situ:** Se utilizará un conjunto pequeño de observaciones de terreno (aprox. 15-20 puntos) correspondientes a la misma ventana temporal de la escena satelital.
* **Emparejamiento:** Se aplicará una ventana temporal estricta ($\pm 3$ días) y una validación espacial para asegurar que los puntos de monitoreo coincidan con píxeles válidos (sin nubes/sombras) del insumo satelital.

## 4. Alcance del Entrenamiento (Scientific)
* **Algoritmo:** Se entrenará un único modelo de regresión lineal simple (o Random Forest base) utilizando NDCI como variable predictora de la Clorofila-a.
* **Límite de hiperparámetros:** El entrenamiento tendrá una configuración fija. No se incluirá optimización de hiperparámetros (GridSearch) ni validación cruzada espacial (Leave-One-Lake-Out) en esta iteración.
* **Baseline:** Se comparará contra un modelo de referencia (promedio histórico simple) sobre la partición de evaluación.

## 5. Estimación y Resultados
* El resultado demostrará la capacidad del worker asíncrono para generar un artefacto de modelo trazable.
* Las estimaciones se limitarán a puntos georreferenciados específicos en el lago, sin generar un mapa continuo rasterizado completo en la interfaz web por el momento.
* Se documentarán explícitamente las advertencias de "condición experimental" al consultar la API.