CREATE SCHEMA IF NOT EXISTS library;

CREATE TABLE IF NOT EXISTS library.versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'published', 'withdrawn')),
    attribution JSONB NOT NULL
        CHECK (
            jsonb_typeof(attribution) = 'object'
            AND attribution ?& ARRAY['author', 'license', 'version', 'source']
            AND jsonb_typeof(attribution->'author') = 'object'
            AND jsonb_typeof(attribution->'source') = 'object'
            AND length(trim(COALESCE(attribution->'source'->>'name', ''))) > 0
            AND jsonb_typeof(attribution->'version') = 'string'
            AND length(trim(attribution->>'version')) > 0
            AND (
                jsonb_typeof(attribution->'license') = 'null'
                OR (
                    jsonb_typeof(attribution->'license') = 'object'
                    AND length(trim(COALESCE(attribution->'license'->>'spdx_id', ''))) > 0
                )
            )
        ),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_library_versions_resource_created
ON library.versions (resource_id, created_at DESC);

ALTER TABLE library.versions ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA library TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA library
TO service_role;
