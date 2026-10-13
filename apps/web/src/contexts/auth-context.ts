import { createContext } from 'react';
import type { User as SupabaseUser } from '@supabase/supabase-js';

export type User = SupabaseUser;

export interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (credentials: { email: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);