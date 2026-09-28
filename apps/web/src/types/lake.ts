import type { GeoJsonGeometry } from './common';

export interface Station {
  id: string;
  lake_id: string;
  code: string;
  name: string;
  description?: string | null;
  geom: GeoJsonGeometry;
  status: 'ACTIVE' | 'INACTIVE' | 'MAINTENANCE';
  created_at?: string;
  updated_at?: string;
}

export interface Lake {
  id: string;
  name: string;
  region: string;
  description?: string | null;
  geom?: GeoJsonGeometry;
  status: 'ACTIVE' | 'INACTIVE';
  created_at?: string;
  updated_at?: string;
  station_count?: number;
  stations?: Station[];
}

export type LakeDetailResponse = Lake;
export type LakeSummary = Omit<Lake, 'geom' | 'description' | 'stations'>;
