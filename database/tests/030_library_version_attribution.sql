BEGIN;

DO $$
DECLARE
    test_org_id UUID;
    test_resource_id UUID;
    test_version_id UUID;
    suffix TEXT := gen_random_uuid()::TEXT;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_attribute
        WHERE attrelid = 'public.organizations'::REGCLASS
          AND attname = 'identifier'
          AND attnotnull
          AND NOT attisdropped
    ) THEN
        EXECUTE
            'INSERT INTO public.organizations (name, identifier) VALUES ($1, $2) RETURNING id'
            INTO test_org_id
            USING 'S3-12 org ' || suffix, 's3-12-' || suffix;
    ELSE
        INSERT INTO public.organizations (name)
        VALUES ('S3-12 org ' || suffix)
        RETURNING id INTO test_org_id;
    END IF;

    INSERT INTO library.resources (owner_organization_id, title, resource_type)
    VALUES (test_org_id, 'S3-12 resource ' || suffix, 'dataset')
    RETURNING id INTO test_resource_id;

    -- Inserción válida con licencia explícita y URL HTTPS
    INSERT INTO library.resource_versions (
        resource_id,
        version,
        author,
        license,
        source,
        created_by
    )
    VALUES (
        test_resource_id,
        '1.2.0',
        '{"status":"known","name":"María Pérez","orcid":"0000-0002-1825-0097"}'::JSONB,
        '{"spdx_id":"CC-BY-4.0","url":"https://creativecommons.org/licenses/by/4.0/"}'::JSONB,
        '{"name":"Repositorio Lago Azul","url":"https://example.org/lago-azul"}'::JSONB,
        NULL
    )
    RETURNING id INTO test_version_id;

    IF NOT EXISTS (
        SELECT 1
        FROM library.resource_versions
        WHERE id = test_version_id
          AND license->>'spdx_id' = 'CC-BY-4.0'
          AND source->>'name' = 'Repositorio Lago Azul'
    ) THEN
        RAISE EXCEPTION 'No se conservó license y source en library.resource_versions.';
    END IF;

    -- Rechaza URL sin esquema http/https en license
    BEGIN
        INSERT INTO library.resource_versions (
            resource_id, version, author, license, source
        )
        VALUES (
            test_resource_id,
            '1.2.1',
            '{"status":"known","name":"María Pérez","orcid":null}'::JSONB,
            '{"spdx_id":"CC-BY-4.0","url":"ftp://invalid.example.org"}'::JSONB,
            '{"name":"Repositorio Lago Azul","url":null}'::JSONB
        );
        RAISE EXCEPTION 'Se permitió license.url sin esquema http/https.';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    -- Rechaza ORCID con formato inválido
    BEGIN
        INSERT INTO library.resource_versions (
            resource_id, version, author, license, source
        )
        VALUES (
            test_resource_id,
            '1.2.2',
            '{"status":"known","name":"María Pérez","orcid":"orcid-invalido"}'::JSONB,
            NULL,
            '{"name":"Repositorio Lago Azul","url":null}'::JSONB
        );
        RAISE EXCEPTION 'Se permitió un ORCID con formato inválido.';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    -- Rechaza versión sin procedencia (source.name vacío)
    BEGIN
        INSERT INTO library.resource_versions (
            resource_id, version, author, license, source
        )
        VALUES (
            test_resource_id,
            '1.2.3',
            '{"status":"unknown","name":null,"orcid":null}'::JSONB,
            NULL,
            '{"name":"   ","url":null}'::JSONB
        );
        RAISE EXCEPTION 'Se permitió una versión sin nombre de procedencia.';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;
END;
$$;

ROLLBACK;
