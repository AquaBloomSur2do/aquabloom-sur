ALTER TABLE dataset.versions
  DROP CONSTRAINT IF EXISTS versions_status_check,
  DROP CONSTRAINT IF EXISTS dataset_versions_status_check,
  DROP CONSTRAINT IF EXISTS versions_state_check,
  DROP CONSTRAINT IF EXISTS dataset_versions_state_check;

ALTER TABLE dataset.versions ADD COLUMN IF NOT EXISTS state VARCHAR(50) DEFAULT 'DRAFT';

UPDATE dataset.versions
SET state = UPPER(COALESCE(state, status, 'DRAFT')),
    status = UPPER(COALESCE(status, state, 'DRAFT'));

ALTER TABLE dataset.versions
  ADD CONSTRAINT dataset_versions_state_check CHECK (state IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED')),
  ADD CONSTRAINT dataset_versions_status_check CHECK (status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED'));
  