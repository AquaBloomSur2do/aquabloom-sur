import { useContext } from 'react';
import { AuthContext } from './auth-context';
import type { AuthContextType } from './auth-context';

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe utilizarse dentro de un AuthProvider.');
  }
  return context;
};