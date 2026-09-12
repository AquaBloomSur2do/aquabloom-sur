-- Archivo: database/seeds/00_roles.sql
-- Orden de ejecución: 1 (Requisito base para dependencias de perfiles)

INSERT INTO public.roles (id, name)
VALUES 
    (gen_random_uuid(), 'visitor'),
    (gen_random_uuid(), 'researcher'),
    (gen_random_uuid(), 'curator'),
    (gen_random_uuid(), 'administrator')
ON CONFLICT (name) DO NOTHING;
