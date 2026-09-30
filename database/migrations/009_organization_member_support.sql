ALTER TABLE public.organizations
ADD COLUMN IF NOT EXISTS identifier VARCHAR(100);

UPDATE public.organizations
SET identifier = trim(both '-' from regexp_replace(lower(name), '[^a-z0-9]+', '-', 'g'))
    || '-' || substring(replace(id::text, '-', '') from 1 for 8)
WHERE identifier IS NULL OR identifier = '';

ALTER TABLE public.organizations
ALTER COLUMN identifier SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_identifier
ON public.organizations USING btree (identifier);

ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS email TEXT;

GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.organizations TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.memberships TO service_role;
GRANT SELECT ON public.profiles TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.stations TO service_role;