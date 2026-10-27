ALTER TABLE dataset.datasets
ADD COLUMN IF NOT EXISTS organization_id UUID
REFERENCES public.organizations(id) ON DELETE CASCADE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'datasets_organization_required'
          AND conrelid = 'dataset.datasets'::regclass
    ) THEN
        ALTER TABLE dataset.datasets
        ADD CONSTRAINT datasets_organization_required
        CHECK (organization_id IS NOT NULL) NOT VALID;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_dataset_datasets_organization
ON dataset.datasets (organization_id);

CREATE OR REPLACE FUNCTION dataset.has_dataset_read_access(
    target_organization_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.memberships AS organization_membership
        WHERE organization_membership.organization_id = target_organization_id
          AND organization_membership.user_id = auth.uid()
          AND organization_membership.status = 'active'
          AND lower(organization_membership.role) IN (
              'admin',
              'administrador',
              'supervisor',
              'investigador',
              'auditor'
          )
    );
$$;

CREATE OR REPLACE FUNCTION dataset.has_dataset_approval_access(
    target_organization_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.memberships AS organization_membership
        WHERE organization_membership.organization_id = target_organization_id
          AND organization_membership.user_id = auth.uid()
          AND organization_membership.status = 'active'
          AND lower(organization_membership.role) IN (
              'admin',
              'administrador',
              'supervisor'
          )
    );
$$;

REVOKE ALL ON FUNCTION dataset.has_dataset_read_access(UUID) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION dataset.has_dataset_approval_access(UUID) FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA dataset TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA dataset TO authenticated;
GRANT INSERT ON dataset.decisions TO authenticated;
GRANT EXECUTE ON FUNCTION dataset.has_dataset_read_access(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION dataset.has_dataset_approval_access(UUID)
TO authenticated;
REVOKE ALL ON SCHEMA dataset FROM anon;
REVOKE ALL ON ALL TABLES IN SCHEMA dataset FROM anon;

DROP POLICY IF EXISTS dataset_datasets_select_organization
ON dataset.datasets;
CREATE POLICY dataset_datasets_select_organization
ON dataset.datasets
FOR SELECT
TO authenticated
USING (dataset.has_dataset_read_access(organization_id));

DROP POLICY IF EXISTS dataset_versions_select_organization
ON dataset.versions;
CREATE POLICY dataset_versions_select_organization
ON dataset.versions
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM dataset.datasets AS parent_dataset
        WHERE parent_dataset.id = versions.dataset_id
          AND dataset.has_dataset_read_access(
              parent_dataset.organization_id
          )
    )
);

DROP POLICY IF EXISTS dataset_memberships_select_organization
ON dataset.memberships;
CREATE POLICY dataset_memberships_select_organization
ON dataset.memberships
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM dataset.versions AS parent_version
        JOIN dataset.datasets AS parent_dataset
          ON parent_dataset.id = parent_version.dataset_id
        WHERE parent_version.id = memberships.version_id
          AND dataset.has_dataset_read_access(
              parent_dataset.organization_id
          )
    )
);

DROP POLICY IF EXISTS dataset_decisions_select_organization
ON dataset.decisions;
CREATE POLICY dataset_decisions_select_organization
ON dataset.decisions
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM dataset.memberships AS parent_membership
        JOIN dataset.versions AS parent_version
          ON parent_version.id = parent_membership.version_id
        JOIN dataset.datasets AS parent_dataset
          ON parent_dataset.id = parent_version.dataset_id
        WHERE parent_membership.id = decisions.membership_id
          AND dataset.has_dataset_read_access(
              parent_dataset.organization_id
          )
    )
);

DROP POLICY IF EXISTS dataset_decisions_insert_approver
ON dataset.decisions;
CREATE POLICY dataset_decisions_insert_approver
ON dataset.decisions
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM dataset.memberships AS parent_membership
        JOIN dataset.versions AS parent_version
          ON parent_version.id = parent_membership.version_id
        JOIN dataset.datasets AS parent_dataset
          ON parent_dataset.id = parent_version.dataset_id
        WHERE parent_membership.id = decisions.membership_id
          AND dataset.has_dataset_approval_access(
              parent_dataset.organization_id
          )
    )
);
