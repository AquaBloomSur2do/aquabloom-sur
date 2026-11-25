-- Creación del esquema aislado para el dominio científico (SQL-145 / S2-145)
CREATE SCHEMA IF NOT EXISTS scientific;

-- Tipos enumerados idempotentes para integridad estricta a nivel de motor SQL
DO $$
BEGIN
    CREATE TYPE scientific.job_type AS ENUM (
        'TRAINING',
        'ESTIMATION'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE scientific.job_status AS ENUM (
        'PENDING',
        'IN_PROGRESS',
        'COMPLETED',
        'FAILED',
        'CANCELLED'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Tabla principal de persistencia de trabajos asíncronos
CREATE TABLE IF NOT EXISTS scientific.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type scientific.job_type NOT NULL,
    status scientific.job_status NOT NULL DEFAULT 'PENDING',
    dataset_version_id UUID REFERENCES dataset.versions(id) ON DELETE SET NULL,
    model_version_id UUID,
    requested_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
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
