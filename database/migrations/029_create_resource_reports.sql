CREATE TABLE public.resource_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type TEXT NOT NULL CHECK (resource_type IN ('lake', 'station')),
    resource_id UUID NOT NULL,
    reported_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    details TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved')),
    resolution_reason TEXT,
    resolved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT resource_reports_resolution_consistency CHECK (
        (status = 'open'
            AND resolution_reason IS NULL
            AND resolved_by IS NULL
            AND resolved_at IS NULL)
        OR
        (status = 'resolved'
            AND resolution_reason IS NOT NULL
            AND length(trim(resolution_reason)) > 0
            AND resolved_by IS NOT NULL
            AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX idx_resource_reports_reporter_created
ON public.resource_reports (reported_by, created_at DESC);

CREATE INDEX idx_resource_reports_status_created
ON public.resource_reports (status, created_at DESC);

ALTER TABLE public.resource_reports ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.resource_reports FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.resource_reports TO service_role;
