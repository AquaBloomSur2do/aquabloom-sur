-- ==============================================================================
-- Tarea S2-111: Migración de Escenas al Dominio Satellite y Adición de Metadatos
-- ==============================================================================

-- 1. Crear el esquema Satellite (si no existe)
CREATE SCHEMA IF NOT EXISTS satellite;

-- 2. Mover la tabla desde public hacia el dominio aislado satellite
ALTER TABLE IF EXISTS public.scenes SET SCHEMA satellite;

-- 3. Agregar las columnas requeridas por los criterios de aceptación
ALTER TABLE satellite.scenes
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS file_references JSONB DEFAULT '[]'::jsonb;

-- 4. Asegurar permisos en el nuevo esquema
GRANT USAGE ON SCHEMA satellite TO service_role;
GRANT ALL ON satellite.scenes TO service_role;

