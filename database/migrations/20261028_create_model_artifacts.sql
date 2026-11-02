CREATE TABLE IF NOT EXISTS public.model_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    training_job_id UUID NOT NULL
        REFERENCES public.scientific_jobs(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_size BIGINT NOT NULL CHECK (file_size > 0),
    checksum TEXT NOT NULL CHECK (checksum ~ '^[a-f0-9]{64}$'),
    storage_path TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (training_job_id)
);

ALTER TABLE public.model_artifacts ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.model_artifacts TO service_role;

INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('model_artifacts', 'model_artifacts', false, 104857600)
ON CONFLICT (id) DO NOTHING;
