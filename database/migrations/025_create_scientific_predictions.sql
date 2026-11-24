CREATE TABLE IF NOT EXISTS scientific.predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id UUID NOT NULL,
    scene_id UUID NOT NULL REFERENCES satellite.scenes(id) ON DELETE RESTRICT,
    result JSONB NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    rules JSONB NOT NULL CHECK (jsonb_typeof(rules) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE scientific.predictions ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON scientific.predictions TO service_role;

CREATE INDEX IF NOT EXISTS idx_scientific_predictions_model_version_id
ON scientific.predictions (model_version_id);

CREATE INDEX IF NOT EXISTS idx_scientific_predictions_scene_id
ON scientific.predictions (scene_id);
