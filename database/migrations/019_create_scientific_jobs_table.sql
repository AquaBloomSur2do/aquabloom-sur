-- Creación del esquema aislado para el dominio científico (S2-145)
CREATE SCHEMA IF NOT EXISTS scientific;

-- Tipos enumerados para integridad estricta a nivel de motor SQL
CREATE TYPE scientific.job_type AS ENUM (
    'TRAINING',
    'ESTIMATION'
);

CREATE TYPE scientific.job_status AS ENUM (
    'PENDING',
    'IN_PROGRESS',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);

-- Tabla principal de persistencia de trabajos asíncronos
CREATE TABLE IF NOT EXISTS scientific.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    job_type scientific.job_type NOT NULL,
    status scientific.job_status NOT NULL DEFAULT 'PENDING',
    
    -- Relaciones e Integridad Referencial (Llaves Foráneas estrictas)
    dataset_version_id UUID REFERENCES dataset.versions(id) ON DELETE SET NULL,
    model_version_id UUID, -- TODO: Referenciar model_versions(id) en tareas futuras cuando se cree la tabla
    
    -- Trazabilidad de Auditoría
    requested_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    
    -- Control de Tiempos
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadatos y Artefactos Resultantes (Estructura flexible)
    result_metadata JSONB DEFAULT '{}'::jsonb,
    error_message TEXT
);

-- Índices para optimización de consultas de trabajadores y dashboard
CREATE INDEX IF NOT EXISTS idx_scientific_jobs_status ON scientific.jobs(status);
CREATE INDEX IF NOT EXISTS idx_scientific_jobs_dataset_version ON scientific.jobs(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_scientific_jobs_requested_by ON scientific.jobs(requested_by);

-- Habilitar Seguridad a Nivel de Filas (RLS) y otorgar permisos
ALTER TABLE scientific.jobs ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA scientific TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON scientific.jobs TO service_role;

