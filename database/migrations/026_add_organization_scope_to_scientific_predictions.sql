-- ==============================================================================
-- Tarea S2-174: Alcance por organización para consulta de detalle de estimaciones
-- ==============================================================================

ALTER TABLE scientific.predictions
    ADD COLUMN IF NOT EXISTS organization_id UUID
    REFERENCES public.organizations(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_scientific_predictions_organization_id
    ON scientific.predictions (organization_id);

CREATE INDEX IF NOT EXISTS idx_scientific_predictions_org_created_at
    ON scientific.predictions (organization_id, created_at DESC);




