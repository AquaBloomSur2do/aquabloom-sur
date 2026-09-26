import { Navigate, Outlet } from 'react-router-dom';
import type { Session } from '@supabase/supabase-js';

interface ProtectedRouteProps {
  session: Session | null;
  redirectPath?: string;
}

export const ProtectedRoute = ({ session, redirectPath = '/login' }: ProtectedRouteProps) => {
  if (!session) {
    return <Navigate to={redirectPath} replace />;
  }

  return <Outlet />;
};
