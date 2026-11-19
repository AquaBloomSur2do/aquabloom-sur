CREATE TABLE IF NOT EXISTS public.samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id UUID NOT NULL REFERENCES public.stations(id) ON DELETE CASCADE,
    import_id UUID REFERENCES public.imports(id) ON DELETE SET NULL,
    sample_datetime_utc TIMESTAMPTZ NOT NULL,
    chlorophyll_a_ug_l DOUBLE PRECISION,
    is_quarantined BOOLEAN DEFAULT FALSE,
    quarantine_reason VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_samples_station_datetime
ON public.samples (station_id, sample_datetime_utc DESC);
