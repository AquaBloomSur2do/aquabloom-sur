-- Archivo: database/migrations/000_create_roles_table.sql
-- Migración inicial: Creación del catálogo de roles

CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);
