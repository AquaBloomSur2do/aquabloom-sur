CREATE TABLE IF NOT EXISTS public.scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id UUID NOT NULL REFERENCES public.lakes(id),
    scene_identifier TEXT NOT NULL,
    acquisition_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT scenes_lake_identifier_unique UNIQUE (lake_id, scene_identifier)
);

CREATE INDEX IF NOT EXISTS idx_scenes_lake_acquisition_date
ON public.scenes (lake_id, acquisition_date DESC);

GRANT SELECT ON public.scenes TO service_role;
