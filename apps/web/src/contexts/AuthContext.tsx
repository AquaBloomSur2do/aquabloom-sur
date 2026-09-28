import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { AuthContext } from './auth-context';
import type { AuthContextType, User } from './auth-context';
import { supabase } from '../lib/supabase';

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (isMounted) {
        setUser(session?.user ?? null);
        setToken(session?.access_token ?? null);
      }
    });

    const restoreSession = async () => {
      try {
        const {
          data: { session },
          error,
        } = await supabase.auth.getSession();

        if (error) throw error;
        if (isMounted) {
          setUser(session?.user ?? null);
          setToken(session?.access_token ?? null);
        }
      } catch (error) {
        console.error('No se pudo restaurar la sesión de autenticación.', error);
        if (isMounted) {
          setUser(null);
          setToken(null);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    void restoreSession();

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const login: AuthContextType['login'] = async (credentials) => {
    const { data, error } = await supabase.auth.signInWithPassword(credentials);
    if (error) throw error;

    setUser(data.user);
    setToken(data.session.access_token);
  };

  const logout: AuthContextType['logout'] = async () => {
    const { error } = await supabase.auth.signOut();
    setUser(null);
    setToken(null);
    if (error) throw error;
  };

  if (isLoading) {
    return <div role="status">Cargando sesión...</div>;
  }

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};