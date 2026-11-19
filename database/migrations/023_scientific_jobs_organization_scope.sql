ALTER TABLE public.scientific_jobs
    ADD COLUMN IF NOT EXISTS organization_id UUID
        REFERENCES public.organizations(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS requested_by UUID
        REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_scientific_jobs_organization_id
    ON public.scientific_jobs (organization_id);

DROP INDEX IF EXISTS public.uq_scientific_jobs_idempotency_key;

CREATE UNIQUE INDEX uq_scientific_jobs_idempotency_key
    ON public.scientific_jobs (organization_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND organization_id IS NOT NULL;
