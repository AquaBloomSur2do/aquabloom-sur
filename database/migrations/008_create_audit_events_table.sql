-- Crear la tabla audit_events
CREATE TABLE IF NOT EXISTS public.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor UUID NOT NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(255) NOT NULL,
    resource_id UUID NOT NULL,
    event_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    organization_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Crear la función que impide la modificación de los campos protegidos
CREATE OR REPLACE FUNCTION public.prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Operación denegada: los eventos de auditoría son inmutables';
END;
$$ LANGUAGE plpgsql;

-- Asociar el trigger a la tabla para garantizar la inmutabilidad de los campos
CREATE TRIGGER enforce_audit_events_immutability
BEFORE UPDATE ON public.audit_events
FOR EACH ROW
EXECUTE FUNCTION public.prevent_audit_update();
