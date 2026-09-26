import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useState, useEffect } from 'react';
import type { Session } from '@supabase/supabase-js';

import { PublicLayout } from './layouts/PublicLayout';
import { PrivateLayout } from './layouts/PrivateLayout';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { LakesList } from './pages/LakesList';
import { LakeDetail } from './pages/LakeDetail';
import { NotFound } from './pages/NotFound';
import { ProtectedRoute } from './components/ProtectedRoute';
import LakeCreate from './pages/LakeCreate';

import Error401 from './pages/Error401';
import Error403 from './pages/Error403';

import { supabase } from './lib/supabase';

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
            
            {/* INYECCIÓN ESTRATÉGICA: /new debe ir antes de /:id */}
            <Route path="/lakes/new" element={<LakeCreate />} />
            
            <Route path="/lakes/:id" element={<LakeDetail />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

