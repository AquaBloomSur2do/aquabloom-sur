-- Migration 017: Alinear estados del ciclo de vida en dataset.versions
ALTER TABLE dataset.versions
  ADD COLUMN IF NOT EXISTS state VARCHAR(50) DEFAULT 'DRAFT';

-- Normalizar datos históricos
UPDATE dataset.versions
SET state = UPPER(COALESCE(status, 'DRAFT'))
WHERE state IS NULL OR state = 'DRAFT';

UPDATE dataset.versions
SET status = state
WHERE status IS NULL OR status != state;

-- Actualizar o crear la restricción de estados permitidos
ALTER TABLE dataset.versions
  DROP CONSTRAINT IF EXISTS dataset_versions_status_check,
  DROP CONSTRAINT IF EXISTS dataset_versions_state_check;

ALTER TABLE dataset.versions
  ADD CONSTRAINT dataset_versions_state_check
  CHECK (state IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED'));
