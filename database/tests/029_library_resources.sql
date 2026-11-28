BEGIN;

DO $$
DECLARE
    test_organization_id UUID;
    test_lake_id UUID;
    test_resource_id UUID;
    test_private_resource_id UUID;
    test_version_id UUID;
    test_organization_suffix TEXT := gen_random_uuid()::TEXT;
    test_organization_name TEXT;
    test_resource_title TEXT;
    test_lake_name TEXT := 'S3-08 test lake ' || gen_random_uuid()::TEXT;
BEGIN
    test_organization_name := 'S3-08 test organization ' || test_organization_suffix;
    test_resource_title := 'S3-08 test resource ' || test_organization_suffix;

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
            INTO test_organization_id
            USING test_organization_name, 's3-08-' || test_organization_suffix;
    ELSE
        INSERT INTO public.organizations (name)
        VALUES (test_organization_name)
        RETURNING id INTO test_organization_id;
    END IF;

    INSERT INTO public.lakes (name, region, geom)
    VALUES (
        test_lake_name,
        'Test region',
        ST_GeomFromText(
            'POLYGON((-73 -40, -72 -40, -72 -39, -73 -39, -73 -40))',
            4326
        )
    )
    RETURNING id INTO test_lake_id;

    INSERT INTO library.resources (
        owner_organization_id,
        title,
        resource_type,
        lake_id,
        visibility
    )
    VALUES (
        test_organization_id,
        test_resource_title,
        'document',
        test_lake_id,
        'public'
    )
    RETURNING id INTO test_resource_id;

    INSERT INTO library.resource_versions (
        resource_id,
        version,
        author,
        license,
        source
    )
    VALUES (
        test_resource_id,
        '1.0.0',
        '{"status":"known","name":"S3-08 test author","orcid":null}'::JSONB,
        '{"spdx_id":"CC-BY-4.0","url":null}'::JSONB,
        '{"name":"S3-08 test source","url":null}'::JSONB
    )
    RETURNING id INTO test_version_id;

    IF NOT EXISTS (
        SELECT 1
        FROM library.resources AS resource
        JOIN library.resource_versions AS resource_version
          ON resource_version.resource_id = resource.id
        WHERE resource.id = test_resource_id
          AND resource_version.id = test_version_id
          AND resource.owner_organization_id = test_organization_id
          AND resource.lake_id = test_lake_id
          AND resource.visibility = 'public'
          AND resource_version.status = 'draft'
    ) THEN
        RAISE EXCEPTION 'No se persistieron los metadatos mínimos del recurso y su versión.';
    END IF;

    INSERT INTO library.resources (
        owner_organization_id,
        title,
        resource_type
    )
    VALUES (
        test_organization_id,
        test_resource_title || ' private',
        'report'
    )
    RETURNING id INTO test_private_resource_id;

    INSERT INTO library.resource_versions (
        resource_id,
        version,
        author,
        license,
        source
    )
    VALUES (
        test_private_resource_id,
        '0.1.0-alpha.1',
        '{"status":"unknown","name":null,"orcid":null}'::JSONB,
        NULL,
        '{"name":"S3-08 historical import","url":null}'::JSONB
    );

    IF NOT EXISTS (
        SELECT 1
        FROM library.resources AS resource
        JOIN library.resource_versions AS resource_version
          ON resource_version.resource_id = resource.id
        WHERE resource.id = test_private_resource_id
          AND resource.lake_id IS NULL
          AND resource.visibility = 'private'
          AND resource_version.version = '0.1.0-alpha.1'
          AND resource_version.author->>'status' = 'unknown'
          AND resource_version.license IS NULL
    ) THEN
        RAISE EXCEPTION 'No se aceptaron los valores opcionales y predeterminados del contrato.';
    END IF;

    BEGIN
        INSERT INTO library.resources (
            owner_organization_id,
            title,
            resource_type,
            lake_id
        )
        VALUES (
            test_organization_id,
            test_resource_title,
            'document',
            test_lake_id
        );
        RAISE EXCEPTION 'Se permitió repetir el título dentro de la misma organización.';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    BEGIN
        INSERT INTO library.resource_versions (
            resource_id,
            version,
            author,
            license,
            source
        )
        VALUES (
            test_resource_id,
            '1.0.0',
            '{"status":"known","name":"S3-08 test author"}'::JSONB,
            '{"spdx_id":"CC-BY-4.0"}'::JSONB,
            '{"name":"S3-08 test source","url":null}'::JSONB
        );
        RAISE EXCEPTION 'Se permitió repetir la versión dentro del mismo recurso.';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    BEGIN
        INSERT INTO library.resources (
            owner_organization_id,
            title,
            resource_type,
            visibility
        )
        VALUES (
            test_organization_id,
            test_resource_title || ' invalid visibility',
            'document',
            'internal'
        );
        RAISE EXCEPTION 'Se permitió una visibilidad inválida.';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        INSERT INTO library.resource_versions (
            resource_id,
            version,
            author,
            license,
            source
        )
        VALUES (
            test_resource_id,
            '1.0',
            '{"status":"known","name":"S3-08 test author"}'::JSONB,
            NULL,
            '{"name":"S3-08 test source","url":null}'::JSONB
        );
        RAISE EXCEPTION 'Se permitió una versión SemVer inválida.';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        INSERT INTO library.resource_versions (
            resource_id,
            version,
            author,
            license,
            source
        )
        VALUES (
            test_resource_id,
            '2.0.0',
            '{"status":"unknown","name":null,"orcid":"0000-0001-2345-6789"}'::JSONB,
            NULL,
            '{"name":"S3-08 test source","url":null}'::JSONB
        );
        RAISE EXCEPTION 'Se permitió un ORCID para un autor desconocido.';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;
END;
$$;

ROLLBACK;
