CREATE TABLE IF NOT EXISTS public.resource_review_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES dataset.versions(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'approved', 'changes_requested', 'withdrawn')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resource_review_requests_version_created
ON public.resource_review_requests (version_id, created_at DESC);

ALTER TABLE public.resource_review_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can read own review requests" ON public.resource_review_requests;
CREATE POLICY "Authenticated users can read own review requests"
ON public.resource_review_requests
FOR SELECT
TO authenticated
USING (auth.uid() = author_id);

DROP POLICY IF EXISTS "Authenticated users can insert own review requests" ON public.resource_review_requests;
CREATE POLICY "Authenticated users can insert own review requests"
ON public.resource_review_requests
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = author_id AND status = 'submitted');

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.resource_review_requests
TO service_role;

GRANT SELECT, INSERT
ON TABLE public.resource_review_requests
TO authenticated;
