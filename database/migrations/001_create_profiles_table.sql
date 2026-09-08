-- Migración S2-013: Tabla perfiles

CREATE TABLE IF NOT EXISTS public.profiles (
    -- Al usar PRIMARY KEY referenciando a auth.users, el motor de base de datos
    -- bloquea automáticamente cualquier intento de crear un segundo perfil.
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    
    name TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Automatización de la marca de tiempo 'updated_at'
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_profiles_updated_at
BEFORE UPDATE ON public.profiles
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();