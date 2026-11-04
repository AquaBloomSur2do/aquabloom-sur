CREATE TABLE IF NOT EXISTS dataset.candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL
        REFERENCES dataset.datasets(id) ON DELETE CASCADE,
    lake_id UUID NOT NULL
        REFERENCES public.lakes(id) ON DELETE RESTRICT,
    data_uri TEXT NOT NULL CHECK (length(trim(data_uri)) > 0),
    source_provider TEXT NOT NULL
        CHECK (length(trim(source_provider)) > 0),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, lake_id, source_provider, data_uri)
);

CREATE TABLE IF NOT EXISTS dataset.candidate_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL
        REFERENCES dataset.candidates(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    decided_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_candidates_dataset_submitted
ON dataset.candidates (dataset_id, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_dataset_candidate_decisions_candidate_decided
ON dataset.candidate_decisions (candidate_id, decided_at DESC);

ALTER TABLE dataset.candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE dataset.candidate_decisions ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE
ON dataset.candidates, dataset.candidate_decisions
TO service_role;

GRANT SELECT, INSERT ON dataset.candidates TO authenticated;
GRANT SELECT, INSERT ON dataset.candidate_decisions TO authenticated;

CREATE POLICY dataset_candidates_select_organization
ON dataset.candidates
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM dataset.datasets AS parent_dataset
        WHERE parent_dataset.id = candidates.dataset_id
          AND dataset.has_dataset_read_access(
              parent_dataset.organization_id
          )
    )
);

CREATE POLICY dataset_candidates_insert_organization
ON dataset.candidates
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM dataset.datasets AS parent_dataset
        WHERE parent_dataset.id = candidates.dataset_id
          AND dataset.has_dataset_read_access(
              parent_dataset.organization_id
          )
    )
);

CREATE POLICY dataset_candidate_decisions_select_organization
ON dataset.candidate_decisions
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM dataset.candidates AS candidate
        JOIN dataset.datasets AS parent_dataset
          ON parent_dataset.id = candidate.dataset_id
        WHERE candidate.id = candidate_decisions.candidate_id
          AND dataset.has_dataset_read_access(
              parent_dataset.organization_id
          )
    )
);

CREATE POLICY dataset_candidate_decisions_insert_approver
ON dataset.candidate_decisions
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM dataset.candidates AS candidate
        JOIN dataset.datasets AS parent_dataset
          ON parent_dataset.id = candidate.dataset_id
        WHERE candidate.id = candidate_decisions.candidate_id
          AND dataset.has_dataset_approval_access(
              parent_dataset.organization_id
          )
    )
);
