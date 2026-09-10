BEGIN;

CREATE INDEX IF NOT EXISTS idx_lakes_geom
ON public.lakes USING gist (geom);

CREATE INDEX IF NOT EXISTS idx_memberships_user_id
ON public.memberships USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_memberships_organization_id
ON public.memberships USING btree (organization_id);

CREATE INDEX IF NOT EXISTS idx_memberships_status
ON public.memberships USING btree (status);

CREATE INDEX IF NOT EXISTS idx_lakes_region
ON public.lakes USING btree (region);

CREATE INDEX IF NOT EXISTS idx_lakes_status
ON public.lakes USING btree (status);

CREATE INDEX IF NOT EXISTS idx_profiles_status
ON public.profiles USING btree (status);

COMMIT;
