import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useState, useEffect } from 'react';
import type { Session } from '@supabase/supabase-js';

import { supabase } from './services/supabase';
import { PublicLayout } from './layouts/PublicLayout';
import { PrivateLayout } from './layouts/PrivateLayout';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { LakesList } from './pages/LakesList';
import { LakeDetail } from './pages/LakeDetail';
import { NotFound } from './pages/NotFound';
import { ProtectedRoute } from './components/ProtectedRoute';

// Importamos la instancia centralizada de Supabase (Patrón Singleton)
import { supabase } from './lib/supabase';

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 1. Obtener la sesion actual al cargar la página
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    // 2. Escuchar cambios automaticamente (cuando el usuario hace login o logout)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    // Limpieza del listener al desmontar el componente
    return () => subscription.unsubscribe();
  }, []);

  // Evitamos el parpadeo de redirección mientras Supabase verifica la sesion
  if (loading) {
    return <div>Cargando sesión...</div>;
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Rutas publicas */}
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
        </Route>

        {/* Rutas privadas (Ahora protegidas dinamicamente) */}
        <Route element={<ProtectedRoute session={session} />}>
          <Route element={<PrivateLayout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/lakes" element={<LakesList />} />
            <Route path="/lakes/:id" element={<LakeDetail />} />
          </Route>
        </Route>

        {/* Ruta 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
