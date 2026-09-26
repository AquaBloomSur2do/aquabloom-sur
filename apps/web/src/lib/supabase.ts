import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  throw new Error(
    'Faltan las variables de entorno de Supabase en el frontend: define VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY en tu archivo .env.'
  );
}

export type { SupabaseClient };

// Única instancia de Supabase para toda la aplicación (Singleton)
export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseKey);
