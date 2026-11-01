-- 1. Insertamos un evento válido
INSERT INTO audit_events (actor, action, resource_type, resource_id, organization_id)
VALUES (
    '11111111-1111-1111-1111-111111111111', 
    'CREATE', 
    'lake', 
    '22222222-2222-2222-2222-222222222222', 
    '33333333-3333-3333-3333-333333333333'
);

-- 2. Intentamos violar la inmutabilidad
UPDATE audit_events 
SET action = 'UPDATE' 
WHERE resource_type = 'lake';