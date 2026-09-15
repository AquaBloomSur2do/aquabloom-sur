BEGIN;

-- B-tree: búsqueda por nombre de lago
CREATE INDEX IF NOT EXISTS idx_lakes_name
ON public.lakes USING btree (name);

-- B-tree: catálogo y filtros de lagos
CREATE INDEX IF NOT EXISTS idx_lakes_region
ON public.lakes USING btree (region);

CREATE INDEX IF NOT EXISTS idx_lakes_status
ON public.lakes USING btree (status);

-- GiST: consultas espaciales sobre geometrías de lagos
CREATE INDEX IF NOT EXISTS idx_lakes_geom
ON public.lakes USING gist (geom);

-- GiST: consultas espaciales sobre puntos de estaciones
CREATE INDEX IF NOT EXISTS idx_stations_point
ON public.stations USING gist (point);

COMMIT;

-- DOWN (reversión)
-- BEGIN;
-- DROP INDEX IF EXISTS public.idx_lakes_name;
-- DROP INDEX IF EXISTS public.idx_lakes_region;
-- DROP INDEX IF EXISTS public.idx_lakes_status;
-- DROP INDEX IF EXISTS public.idx_lakes_geom;
-- DROP INDEX IF EXISTS public.idx_stations_point;
-- COMMIT;
