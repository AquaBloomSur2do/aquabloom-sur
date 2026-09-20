export type LakeStatus = 'active' | 'inactive' | 'maintenance' | 'archived' | string;

export interface LakeStation {
  id: string;
  lake_id: string;
  code: string;
  name: string;
  description?: string | null;
  status: LakeStatus;
  point?: {
    type: 'Point';
    coordinates: [number, number];
  } | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LakeSummary {
  id: string;
  name: string;
  region: string;
  description?: string | null;
  status: LakeStatus;
  station_count?: number;
  stations?: LakeStation[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LakeDetailResponse extends LakeSummary {
  geom?: {
    type: 'Polygon';
    coordinates: number[][][];
  } | null;
}
