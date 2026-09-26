export interface Station {
  id: string;
  code: string;
  name: string;
  status?: string;
}

export interface LakeDetailResponse {
  id: string;
  name: string;
  region: string;
  description?: string;
  status?: string;
  geom?: Record<string, unknown> | string;
  station_count?: number;
  stations?: Station[];
}