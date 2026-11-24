-- ==============================================================================
-- SQL-000 / S2-111: Unificación idempotente de la tabla de escenas en satellite
-- ==============================================================================

-- 1. Asegurar la existencia del esquema aislado satellite
CREATE SCHEMA IF NOT EXISTS satellite;

-- 2. Trasladar la tabla heredada de public.scenes si todavía existiera
ALTER TABLE IF EXISTS public.scenes SET SCHEMA satellite;

-- 3. Crear la tabla base en satellite si no existe (antes en 013_create_scenes)
CREATE TABLE IF NOT EXISTS satellite.scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id UUID NOT NULL REFERENCES public.lakes(id),
    scene_identifier TEXT NOT NULL,
    acquisition_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT scenes_lake_identifier_unique UNIQUE (lake_id, scene_identifier)
);

-- 4. Agregar las columnas de metadatos y referencias de archivo
ALTER TABLE satellite.scenes
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS file_references JSONB DEFAULT '[]'::jsonb;

-- 5. Índice para consultas por lago y fecha de adquisición
CREATE INDEX IF NOT EXISTS idx_scenes_lake_acquisition_date
ON satellite.scenes (lake_id, acquisition_date DESC);

-- 6. Permisos del dominio satellite para el rol de servicio
GRANT USAGE ON SCHEMA satellite TO service_role;
GRANT ALL ON satellite.scenes TO service_role;
