CREATE SCHEMA IF NOT EXISTS dataset;

CREATE TABLE IF NOT EXISTS dataset.datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset.versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES dataset.datasets(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, version_number)
);

CREATE TABLE IF NOT EXISTS dataset.memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES dataset.versions(id) ON DELETE CASCADE,
    scene_provider TEXT NOT NULL CHECK (length(trim(scene_provider)) > 0),
    scene_external_id TEXT NOT NULL CHECK (length(trim(scene_external_id)) > 0),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (version_id, scene_provider, scene_external_id)
);

CREATE TABLE IF NOT EXISTS dataset.decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    membership_id UUID NOT NULL
        REFERENCES dataset.memberships(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    reason TEXT,
    decided_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_versions_dataset_created
ON dataset.versions (dataset_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_dataset_decisions_membership_decided
ON dataset.decisions (membership_id, decided_at DESC);

ALTER TABLE dataset.datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE dataset.versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE dataset.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE dataset.decisions ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA dataset TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA dataset
TO service_role;
