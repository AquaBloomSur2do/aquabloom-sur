CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor UUID NOT NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(255) NOT NULL,
    resource_id UUID NOT NULL,
    event_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    organization_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE OR REPLACE FUNCTION prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.actor <> OLD.actor OR NEW.action <> OLD.action OR NEW.event_date <> OLD.event_date THEN
        RAISE EXCEPTION 'Operación denegada: no se permite modificar actor, acción ni fecha de un evento de auditoría';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_audit_events_immutability
BEFORE UPDATE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_update();

INSERT INTO audit_events (actor, action, resource_type, resource_id, organization_id)
VALUES (
    '11111111-1111-1111-1111-111111111111', 
    'CREATE', 
    'lake', 
    '22222222-2222-2222-2222-222222222222', 
    '33333333-3333-3333-3333-333333333333'
);

UPDATE audit_events 
SET action = 'UPDATE' 
WHERE resource_type = 'lake';
