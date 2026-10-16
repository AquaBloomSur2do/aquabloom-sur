CREATE TABLE IF NOT EXISTS public.prepared_inputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_import_id UUID NOT NULL
        REFERENCES public.imports(id) ON DELETE RESTRICT,
    source_key VARCHAR(255) NOT NULL UNIQUE
        CHECK (length(btrim(source_key)) > 0),
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);