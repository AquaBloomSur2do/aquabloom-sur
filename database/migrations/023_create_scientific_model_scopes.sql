CREATE TABLE IF NOT EXISTS public.scientific_model_scopes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id UUID NOT NULL REFERENCES public.lakes(id) ON DELETE RESTRICT,
    variable VARCHAR(255) NOT NULL CHECK (btrim(variable) <> ''),
    observed_range JSONB NOT NULL CHECK (
        CASE
            WHEN jsonb_typeof(observed_range) = 'object'
                AND jsonb_typeof(observed_range->'minimum') = 'number'
                AND jsonb_typeof(observed_range->'maximum') = 'number'
            THEN (observed_range->>'minimum')::NUMERIC
                <= (observed_range->>'maximum')::NUMERIC
            ELSE FALSE
        END
    ),
    experimental_condition TEXT NOT NULL CHECK (btrim(experimental_condition) <> ''),
    is_validated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE
ON public.scientific_model_scopes TO service_role;
