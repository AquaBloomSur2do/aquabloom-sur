-- Habilitar extensión PostGIS en el esquema public
CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;

-- Crear tabla lakes
CREATE TABLE public.lakes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    region VARCHAR(255) NOT NULL,
    description TEXT,
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Trigger para automatizar la marca de tiempo
CREATE TRIGGER set_lakes_updated_at
BEFORE UPDATE ON public.lakes
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();
