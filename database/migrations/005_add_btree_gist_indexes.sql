BEGIN;

CREATE INDEX IF NOT EXISTS idx_lakes_geom
ON public.lakes USING gist (geom);

-- Optimización de búsquedas en memberships por usuario y organización
CREATE INDEX IF NOT EXISTS idx_memberships_user_id
ON public.memberships USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_memberships_organization_id
ON public.memberships USING btree (organization_id);

CREATE INDEX IF NOT EXISTS idx_memberships_status
ON public.memberships USING btree (status);

-- Optimización de filtros en lakes
CREATE INDEX IF NOT EXISTS idx_lakes_region
ON public.lakes USING btree (region);

CREATE INDEX IF NOT EXISTS idx_lakes_status
ON public.lakes USING btree (status);

-- Optimización de filtros en profiles
CREATE INDEX IF NOT EXISTS idx_profiles_status
ON public.profiles USING btree (status);

COMMIT;

