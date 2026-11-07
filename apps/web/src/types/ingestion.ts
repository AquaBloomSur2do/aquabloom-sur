export interface PreparedInput {
  id: string;
  original_import_id: string;
  source_key: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata: Record<string, any>;
  created_at: string;
}
