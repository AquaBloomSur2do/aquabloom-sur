ALTER TABLE public.profiles
ALTER COLUMN name DROP NOT NULL;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Permitir lectura de perfiles a usuarios autenticados" ON public.profiles;
CREATE POLICY "Permitir lectura de perfiles a usuarios autenticados"
ON public.profiles
FOR SELECT
TO authenticated, service_role
USING (true);

GRANT SELECT ON public.profiles TO authenticated, service_role;
