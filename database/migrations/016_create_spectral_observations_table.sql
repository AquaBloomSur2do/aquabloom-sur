-- ==============================================================================
-- Tarea S2-127: Guardar observaciones espectrales (Dominio Satellite)
-- ==============================================================================

-- 1. Asegurar la existencia del esquema
CREATE SCHEMA IF NOT EXISTS satellite;

-- 2. Crear tabla de observaciones espectrales
-- Cumple el criterio: Persistir bandas, índice, reglas y vínculos (scene_id, sample_id)
CREATE TABLE IF NOT EXISTS satellite.spectral_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID NOT NULL REFERENCES satellite.scenes(id) ON DELETE CASCADE,
    sample_id UUID NOT NULL, -- Referencia lógica al identificador de la muestra in-situ
    bands JSONB NOT NULL,    -- Almacenamiento dinámico de los valores por banda (ej. B04, B08)
    spectral_index VARCHAR(50) NOT NULL,
    index_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50) NOT NULL,
    quality VARCHAR(20) NOT NULL, -- Valores esperados: 'OPTIMA', 'ACEPTABLE', 'RECHAZADA'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Índices para agilizar búsquedas por escena y muestra
CREATE INDEX IF NOT EXISTS idx_spectral_observations_scene_id ON satellite.spectral_observations(scene_id);
CREATE INDEX IF NOT EXISTS idx_spectral_observations_sample_id ON satellite.spectral_observations(sample_id);

-- 4. Permisos
GRANT ALL ON satellite.spectral_observations TO service_role;