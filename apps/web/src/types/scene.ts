export interface Scene {
  id: string;
  lake_id: string;
  scene_identifier: string;
  acquisition_date: string;
  created_at: string;
  provider?: string | null;
  external_id?: string | null;
  cloud_cover?: number | null;
  status?: 'pending' | 'processed' | 'failed' | 'rejected' | null;
}

export interface PaginatedScenes {
  items: Scene[];
  page: number;
  page_size: number;
  total: number;
}
