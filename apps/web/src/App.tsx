import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import type { Session } from '@supabase/supabase-js';
import axios from 'axios';

import { PublicLayout } from './layouts/PublicLayout';
import { PrivateLayout } from './layouts/PrivateLayout';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { LakesList } from './pages/LakesList';
import { LakeDetail } from './pages/LakeDetail';
import { NotFound } from './pages/NotFound';
import { ProtectedRoute } from './components/ProtectedRoute';

import Error401 from './pages/Error401';
import Error403 from './pages/Error403';

import { supabase } from './lib/supabase';
// Importamos el manejador global
import { setupGlobalErrorHandler } from './lib/errorHandler';

// Componente auxiliar para inyectar navigate en Axios con limpieza de memoria
function AxiosInterceptor() {
  const navigate = useNavigate();
  
  useEffect(() => {
    // 1. Configuramos el interceptor y guardamos su ID numérico
    const interceptorId = setupGlobalErrorHandler(navigate);

    // 2. Función de limpieza para expulsar el interceptor y evitar fugas de memoria
    return () => {
      axios.interceptors.response.eject(interceptorId);
    };
  }, [navigate]);

  return null; // Este componente no renderiza nada visualmente
}

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (loading) {
    return <div>Cargando sesión...</div>;
  }

  return (
    <BrowserRouter>
      {/* Inicializamos el interceptor de Axios aquí para que tenga acceso al router */}
      <AxiosInterceptor />
      
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/401" element={<Error401 />} />
          <Route path="/403" element={<Error403 />} />
        </Route>

        <Route element={<ProtectedRoute session={session} />}>
          <Route element={<PrivateLayout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/lakes" element={<LakesList />} />
            <Route path="/lakes/:id" element={<LakeDetail />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
