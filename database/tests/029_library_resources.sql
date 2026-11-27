BEGIN;

DO $$
DECLARE
    test_organization_id UUID;
    test_lake_id UUID;
    test_resource_id UUID;
    test_version_id UUID;
    test_lake_name TEXT := 'S3-08 test lake ' || gen_random_uuid()::TEXT;
BEGIN
    INSERT INTO public.organizations (name)
    VALUES ('S3-08 test organization')
    RETURNING id INTO test_organization_id;

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
        'S3-08 test resource',
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
        '{"status":"known","name":"S3-08 test author"}'::JSONB,
        '{"spdx_id":"CC-BY-4.0"}'::JSONB,
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

    BEGIN
        INSERT INTO library.resources (
            owner_organization_id,
            title,
            resource_type,
            lake_id
        )
        VALUES (
            test_organization_id,
            'S3-08 test resource',
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
END;
$$;

ROLLBACK;
