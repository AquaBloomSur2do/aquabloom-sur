-- Migracion S2-039: estado de las organizaciones para membresias activas

ALTER TABLE public.organizations
ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active' NOT NULL;

CREATE INDEX IF NOT EXISTS idx_organizations_status
ON public.organizations USING btree (status);