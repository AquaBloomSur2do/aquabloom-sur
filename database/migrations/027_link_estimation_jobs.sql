ALTER TABLE public.scientific_jobs
    ADD COLUMN IF NOT EXISTS model_version_id UUID,
    ADD COLUMN IF NOT EXISTS scene_id UUID
        REFERENCES satellite.scenes(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_scientific_jobs_model_version_id
    ON public.scientific_jobs (model_version_id);

CREATE INDEX IF NOT EXISTS idx_scientific_jobs_scene_id
    ON public.scientific_jobs (scene_id);
