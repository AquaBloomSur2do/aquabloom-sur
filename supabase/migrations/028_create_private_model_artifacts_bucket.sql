INSERT INTO storage.buckets (id, name, public)
VALUES ('model_artifacts', 'model_artifacts', FALSE)
ON CONFLICT (id) DO UPDATE SET public = FALSE;

DROP POLICY IF EXISTS model_artifacts_deny_client_access ON storage.objects;

CREATE POLICY model_artifacts_deny_client_access
    ON storage.objects
    AS RESTRICTIVE
    FOR ALL
    TO anon, authenticated
    USING (bucket_id <> 'model_artifacts')
    WITH CHECK (bucket_id <> 'model_artifacts');
    