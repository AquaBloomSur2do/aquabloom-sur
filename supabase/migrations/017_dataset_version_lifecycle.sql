-- Migration 017: Actualizar estados permitidos en dataset_versions
ALTER TABLE dataset_versions
  DROP CONSTRAINT IF EXISTS dataset_versions_state_check;

ALTER TABLE dataset_versions
  ADD CONSTRAINT dataset_versions_state_check
  CHECK (state IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED'));

  