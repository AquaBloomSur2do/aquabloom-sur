CREATE SCHEMA IF NOT EXISTS library;

CREATE TABLE IF NOT EXISTS library.resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_organization_id UUID NOT NULL
        REFERENCES public.organizations(id) ON DELETE CASCADE,
    title TEXT NOT NULL
        CHECK (title = BTRIM(title) AND length(title) BETWEEN 1 AND 200),
    resource_type TEXT NOT NULL
        CHECK (resource_type ~ '^[a-z][a-z0-9_-]{0,63}$'),
    lake_id UUID REFERENCES public.lakes(id) ON DELETE SET NULL,
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'public')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT library_resources_owner_title_key
        UNIQUE (owner_organization_id, title)
);

CREATE TABLE IF NOT EXISTS library.resource_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL
        REFERENCES library.resources(id) ON DELETE CASCADE,
    version TEXT NOT NULL
        CHECK (
            version ~
            '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'
        ),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (
            status IN ('draft', 'submitted', 'approved', 'published', 'withdrawn')
        ),
    author JSONB NOT NULL
        CHECK (
            jsonb_typeof(author) = 'object'
            AND author ? 'status'
            AND jsonb_typeof(author->'status') = 'string'
            AND author ? 'name'
            AND (
                (
                    author->>'status' = 'known'
                    AND jsonb_typeof(author->'name') = 'string'
                    AND length(BTRIM(author->>'name')) > 0
                    AND (
                        NOT (author ? 'orcid')
                        OR author->'orcid' = 'null'::jsonb
                        OR (
                            jsonb_typeof(author->'orcid') = 'string'
                            AND length(BTRIM(author->>'orcid')) > 0
                        )
                    )
                )
                OR (
                    author->>'status' = 'unknown'
                    AND author->'name' = 'null'::jsonb
                    AND (
                        NOT (author ? 'orcid')
                        OR author->'orcid' = 'null'::jsonb
                    )
                )
            )
        ),
    license JSONB
        CHECK (
            license IS NULL
            OR (
                jsonb_typeof(license) = 'object'
                AND license ? 'spdx_id'
                AND jsonb_typeof(license->'spdx_id') = 'string'
                AND length(BTRIM(license->>'spdx_id')) > 0
                AND (
                    NOT (license ? 'url')
                    OR license->'url' = 'null'::jsonb
                    OR (
                        jsonb_typeof(license->'url') = 'string'
                        AND length(BTRIM(license->>'url')) > 0
                    )
                )
            )
        ),
    source JSONB NOT NULL
        CHECK (
            jsonb_typeof(source) = 'object'
            AND source ? 'name'
            AND jsonb_typeof(source->'name') = 'string'
            AND length(BTRIM(source->>'name')) > 0
            AND source ? 'url'
            AND (
                source->'url' = 'null'::jsonb
                OR (
                    jsonb_typeof(source->'url') = 'string'
                    AND length(BTRIM(source->>'url')) > 0
                )
            )
        ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT library_resource_versions_resource_version_key
        UNIQUE (resource_id, version)
);

CREATE INDEX IF NOT EXISTS library_resources_lake_id_idx
    ON library.resources (lake_id);

ALTER TABLE library.resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE library.resource_versions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON SCHEMA library FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA library FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA library FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON SCHEMA library FROM anon;
        REVOKE ALL ON ALL TABLES IN SCHEMA library FROM anon;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA library FROM anon;
        ALTER DEFAULT PRIVILEGES IN SCHEMA library
            REVOKE ALL ON TABLES FROM anon;
        ALTER DEFAULT PRIVILEGES IN SCHEMA library
            REVOKE ALL ON SEQUENCES FROM anon;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON SCHEMA library FROM authenticated;
        REVOKE ALL ON ALL TABLES IN SCHEMA library FROM authenticated;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA library FROM authenticated;
        ALTER DEFAULT PRIVILEGES IN SCHEMA library
            REVOKE ALL ON TABLES FROM authenticated;
        ALTER DEFAULT PRIVILEGES IN SCHEMA library
            REVOKE ALL ON SEQUENCES FROM authenticated;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT USAGE ON SCHEMA library TO service_role;
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON ALL TABLES IN SCHEMA library TO service_role;
        GRANT USAGE, SELECT
            ON ALL SEQUENCES IN SCHEMA library TO service_role;

        ALTER DEFAULT PRIVILEGES IN SCHEMA library
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role;
        ALTER DEFAULT PRIVILEGES IN SCHEMA library
            GRANT USAGE, SELECT ON SEQUENCES TO service_role;
    END IF;

    ALTER DEFAULT PRIVILEGES IN SCHEMA library
        REVOKE ALL ON TABLES FROM PUBLIC;
    ALTER DEFAULT PRIVILEGES IN SCHEMA library
        REVOKE ALL ON SEQUENCES FROM PUBLIC;
END;
$$;
