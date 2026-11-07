import { supabase } from '../lib/supabase';
import type { PreparedInput } from '../types/ingestion';

export const getPreparedInputs = async (): Promise<PreparedInput[]> => {
  const { data, error } = await supabase
    .from('prepared_inputs')
    .select('*')
    .order('created_at', { ascending: false });

  if (error) {
    throw error;
  }

  return data as PreparedInput[];
};
