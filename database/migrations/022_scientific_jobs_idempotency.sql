-- 1. Crear la tabla pública exacta que espera el código con UUID
CREATE TABLE IF NOT EXISTS public.scientific_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL,
    config JSONB NOT NULL,
    status TEXT NOT NULL,
    result JSONB,
    error_message TEXT,
    idempotency_key VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 2. Restricciones estrictas para job_type y status
ALTER TABLE public.scientific_jobs DROP CONSTRAINT IF EXISTS chk_job_type;
ALTER TABLE public.scientific_jobs ADD CONSTRAINT chk_job_type 
    CHECK (job_type IN ('training', 'modeling', 'estimation'));

ALTER TABLE public.scientific_jobs DROP CONSTRAINT IF EXISTS chk_job_status;
ALTER TABLE public.scientific_jobs ADD CONSTRAINT chk_job_status 
    CHECK (status IN ('queued', 'running', 'completed', 'failed'));

-- 3. Índice único parcial para evitar duplicados concurrentes (excluyendo NULL)
DROP INDEX IF EXISTS uq_scientific_jobs_idempotency_key;
CREATE UNIQUE INDEX uq_scientific_jobs_idempotency_key 
    ON public.scientific_jobs (idempotency_key) 
    WHERE idempotency_key IS NOT NULL;

-- 4. Permisos de acceso para la aplicación
GRANT ALL PRIVILEGES ON TABLE public.scientific_jobs TO service_role;
