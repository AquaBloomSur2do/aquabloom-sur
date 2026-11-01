# Regla de Emparejamiento (Matchup) - AquaBloom Sur
**Versión de Regla:** v1.0-piloto

Esta regla define los criterios para relacionar muestras de terreno con observaciones satelitales Sentinel-2 L2A para el desarrollo del piloto experimental (Sprint 2).

## 1. Tolerancias de Coincidencia (Matchup)
* **Ventana Temporal:** ± 3 días respecto a la fecha de adquisición de la escena (`acquisition_date`).
* **Distancia Espacial:** Radio máximo de 50 metros desde las coordenadas de la estación.
* **Sistema de Referencia (SRID):** 
  * Almacenamiento base: SRID 4326 (WGS84).
  * Cálculo de distancia espacial: Reproyección a UTM métrico (EPSG:32718 o 32719 dependiendo de la longitud) para evaluación de distancias.

## 2. Criterios de Calidad (Exclusión de Píxeles)
Un píxel será excluido del matchup si cumple alguna de estas condiciones:
* Clasificado como Nube (alta o media probabilidad).
* Clasificado como Sombra de nube.
* Clasificado como Tierra (Vegetación o Suelo desnudo).
* Píxeles sin datos (NoData).
* Píxeles ubicados dentro del buffer de exclusión costera (determinado por el polígono del lago).