export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
  request_id?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface GeoJsonGeometry {
  type: 'Point' | 'Polygon' | 'MultiPolygon';
  coordinates: unknown[];
}
