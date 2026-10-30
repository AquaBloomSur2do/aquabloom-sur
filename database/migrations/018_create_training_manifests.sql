CREATE TABLE IF NOT EXISTS dataset.training_manifests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES dataset.versions(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    checksum TEXT NOT NULL CHECK (checksum ~ '^[a-f0-9]{64}$'), -- Confianza cero: Solo SHA-256 válido
    variables TEXT[] NOT NULL DEFAULT '{"temperatura", "clorofila_a", "turbidez", "ph"}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(version_id)
);

ALTER TABLE dataset.training_manifests ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON dataset.training_manifests TO service_role;

INSERT INTO storage.buckets (id, name, public)
VALUES ('training_files', 'training_files', false)
ON CONFLICT (id) DO NOTHING;
