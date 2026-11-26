BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM storage.buckets
        WHERE id = 'model_artifacts' AND public = FALSE
    ) THEN
        RAISE EXCEPTION 'El bucket model_artifacts no existe o es publico.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'storage'
          AND tablename = 'objects'
          AND policyname = 'model_artifacts_deny_client_access'
          AND permissive = 'RESTRICTIVE'
    ) THEN
        RAISE EXCEPTION 'Falta la politica restrictiva de model_artifacts.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_class
        WHERE oid = 'storage.objects'::regclass AND relrowsecurity
    ) THEN
        RAISE EXCEPTION 'RLS esta desactivado en storage.objects.';
    END IF;
END;
$$;

INSERT INTO storage.objects (bucket_id, name)
VALUES (
    'model_artifacts',
    'models/28000000-0000-0000-0000-000000000001/model.pkl'
);

-- Politica permisiva "por error": la restrictiva debe seguir bloqueando.
CREATE POLICY s2_185_test_open_access
    ON storage.objects
    FOR ALL
    TO anon, authenticated
    USING (TRUE)
    WITH CHECK (TRUE);

SET LOCAL ROLE anon;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM storage.objects WHERE bucket_id = 'model_artifacts') THEN
        RAISE EXCEPTION 'Un usuario anonimo puede leer artefactos privados.';
    END IF;
END;
$$;

RESET ROLE;
SET LOCAL ROLE authenticated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM storage.objects WHERE bucket_id = 'model_artifacts') THEN
        RAISE EXCEPTION 'Un usuario autenticado puede leer artefactos privados.';
    END IF;

    BEGIN
        INSERT INTO storage.objects (bucket_id, name)
        VALUES (
            'model_artifacts',
            'models/28000000-0000-0000-0000-000000000002/model.pkl'
        );
        RAISE EXCEPTION 'Un usuario autenticado pudo subir un artefacto privado.';
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'Esperado: authenticated no puede escribir en model_artifacts.';
    END;
END;
$$;

ROLLBACK;
