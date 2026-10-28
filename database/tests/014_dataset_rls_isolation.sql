BEGIN;

INSERT INTO auth.users (
    id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    raw_app_meta_data,
    raw_user_meta_data,
    created_at,
    updated_at
)
VALUES
    (
        '13800000-0000-0000-0000-000000000001',
        'authenticated',
        'authenticated',
        's2-138-foreign@example.test',
        '',
        NOW(),
        '{}'::jsonb,
        '{}'::jsonb,
        NOW(),
        NOW()
    ),
    (
        '13800000-0000-0000-0000-000000000002',
        'authenticated',
        'authenticated',
        's2-138-member@example.test',
        '',
        NOW(),
        '{}'::jsonb,
        '{}'::jsonb,
        NOW(),
        NOW()
    ),
    (
        '13800000-0000-0000-0000-000000000003',
        'authenticated',
        'authenticated',
        's2-138-investigator@example.test',
        '',
        NOW(),
        '{}'::jsonb,
        '{}'::jsonb,
        NOW(),
        NOW()
    ),
    (
        '13800000-0000-0000-0000-000000000004',
        'authenticated',
        'authenticated',
        's2-138-supervisor@example.test',
        '',
        NOW(),
        '{}'::jsonb,
        '{}'::jsonb,
        NOW(),
        NOW()
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.organizations (id, name, identifier)
VALUES
    (
        '13800000-0000-0000-0000-000000000010',
        'S2-138 Pilot Organization',
        's2-138-pilot-test'
    ),
    (
        '13800000-0000-0000-0000-000000000011',
        'S2-138 Other Organization',
        's2-138-other-test'
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.memberships (user_id, organization_id, role, status)
VALUES
    (
        '13800000-0000-0000-0000-000000000001',
        '13800000-0000-0000-0000-000000000011',
        'investigador',
        'active'
    ),
    (
        '13800000-0000-0000-0000-000000000002',
        '13800000-0000-0000-0000-000000000010',
        'member',
        'active'
    ),
    (
        '13800000-0000-0000-0000-000000000003',
        '13800000-0000-0000-0000-000000000010',
        'investigador',
        'active'
    ),
    (
        '13800000-0000-0000-0000-000000000004',
        '13800000-0000-0000-0000-000000000010',
        'supervisor',
        'active'
    )
ON CONFLICT (user_id, organization_id) DO NOTHING;

INSERT INTO dataset.datasets (id, organization_id, name)
VALUES (
    '13800000-0000-0000-0000-000000000020',
    '13800000-0000-0000-0000-000000000010',
    'S2-138 pilot dataset'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO dataset.versions (id, dataset_id, version_number)
VALUES (
    '13800000-0000-0000-0000-000000000030',
    '13800000-0000-0000-0000-000000000020',
    1
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO dataset.memberships (
    id,
    version_id,
    scene_provider,
    scene_external_id
)
VALUES (
    '13800000-0000-0000-0000-000000000040',
    '13800000-0000-0000-0000-000000000030',
    'S2-138-test',
    'pilot-scene-1'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO dataset.decisions (
    id,
    membership_id,
    decision,
    decided_by
)
VALUES (
    '13800000-0000-0000-0000-000000000050',
    '13800000-0000-0000-0000-000000000040',
    'accepted',
    '13800000-0000-0000-0000-000000000004'
)
ON CONFLICT (id) DO NOTHING;

SET LOCAL ROLE authenticated;

SELECT set_config(
    'request.jwt.claim.sub',
    '13800000-0000-0000-0000-000000000001',
    TRUE
);
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM dataset.datasets
        WHERE id = '13800000-0000-0000-0000-000000000020'
    ) THEN
        RAISE EXCEPTION 'Foreign organization can read the pilot dataset.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM dataset.versions
        WHERE id = '13800000-0000-0000-0000-000000000030'
    ) THEN
        RAISE EXCEPTION 'Foreign organization can read pilot versions.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM dataset.memberships
        WHERE id = '13800000-0000-0000-0000-000000000040'
    ) THEN
        RAISE EXCEPTION 'Foreign organization can read pilot memberships.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM dataset.decisions
        WHERE id = '13800000-0000-0000-0000-000000000050'
    ) THEN
        RAISE EXCEPTION 'Foreign organization can read pilot decisions.';
    END IF;

    BEGIN
        INSERT INTO dataset.decisions (membership_id, decision)
        VALUES (
            '13800000-0000-0000-0000-000000000040',
            'rejected'
        );
        RAISE EXCEPTION 'Foreign organization inserted an approval decision.';
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'Expected: foreign organization cannot approve.';
    END;
END;
$$;

SELECT set_config(
    'request.jwt.claim.sub',
    '13800000-0000-0000-0000-000000000002',
    TRUE
);
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM dataset.datasets
        WHERE id = '13800000-0000-0000-0000-000000000020'
    ) THEN
        RAISE EXCEPTION 'A role without dataset permission can read the dataset.';
    END IF;

    BEGIN
        INSERT INTO dataset.decisions (membership_id, decision)
        VALUES (
            '13800000-0000-0000-0000-000000000040',
            'accepted'
        );
        RAISE EXCEPTION 'A role without approval permission inserted a decision.';
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'Expected: role without permission cannot approve.';
    END;
END;
$$;

SELECT set_config(
    'request.jwt.claim.sub',
    '13800000-0000-0000-0000-000000000003',
    TRUE
);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM dataset.datasets
        WHERE id = '13800000-0000-0000-0000-000000000020'
    ) THEN
        RAISE EXCEPTION 'Active organization investigator cannot read the dataset.';
    END IF;

    BEGIN
        INSERT INTO dataset.decisions (membership_id, decision)
        VALUES (
            '13800000-0000-0000-0000-000000000040',
            'accepted'
        );
        RAISE EXCEPTION 'An investigator inserted an approval decision.';
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'Expected: investigator cannot approve.';
    END;
END;
$$;

SELECT set_config(
    'request.jwt.claim.sub',
    '13800000-0000-0000-0000-000000000004',
    TRUE
);
INSERT INTO dataset.decisions (membership_id, decision, decided_by)
VALUES (
    '13800000-0000-0000-0000-000000000040',
    'accepted',
    '13800000-0000-0000-0000-000000000004'
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM dataset.decisions
        WHERE membership_id = '13800000-0000-0000-0000-000000000040'
          AND decided_by = '13800000-0000-0000-0000-000000000004'
    ) THEN
        RAISE EXCEPTION 'Authorized supervisor could not approve the scene.';
    END IF;
END;
$$;

ROLLBACK;
