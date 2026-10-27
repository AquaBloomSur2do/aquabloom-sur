export interface Scene {
  id: string;
  lake_id: string;
  scene_identifier: string;
  acquisition_date: string;
  created_at: string;
}

export interface PaginatedScenes {
  items: Scene[];
  page: number;
  page_size: number;
  total: number;
}
