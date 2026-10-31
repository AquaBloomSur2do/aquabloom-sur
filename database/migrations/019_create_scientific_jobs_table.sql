-- Crear esquema para el dominio científico aislando su responsabilidad
CREATE SCHEMA IF NOT EXISTS scientific;

-- Crear tipos enumerados para restringir valores y asegurar integridad
CREATE TYPE scientific.job_status AS ENUM ('queued', 'running', 'completed', 'failed');
CREATE TYPE scientific.job_type AS ENUM ('training', 'modeling', 'estimation');

-- Eliminar la tabla pública si alguien la levantó por error en el entorno local
DROP TABLE IF EXISTS public.scientific_jobs;

-- Crear la tabla principal de trabajos en el esquema correcto (S2-145)
CREATE TABLE IF NOT EXISTS scientific.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type scientific.job_type NOT NULL,
    status scientific.job_status NOT NULL DEFAULT 'queued',
    config JSONB NOT NULL,
    result JSONB DEFAULT '{}'::jsonb,
    dataset_version_id UUID,
    model_version_id UUID,
    requested_by UUID, 
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para optimizar las colas y consultas de estado
CREATE INDEX idx_scientific_jobs_status ON scientific.jobs(status);
CREATE INDEX idx_scientific_jobs_type ON scientific.jobs(job_type);