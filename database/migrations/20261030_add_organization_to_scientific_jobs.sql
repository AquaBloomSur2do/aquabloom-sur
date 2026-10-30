ALTER TABLE public.scientific_jobs
ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE public.scientific_jobs
ADD CONSTRAINT scientific_jobs_organization_id_required
CHECK (organization_id IS NOT NULL) NOT VALID;

CREATE INDEX idx_scientific_jobs_organization_id
ON public.scientific_jobs(organization_id);
