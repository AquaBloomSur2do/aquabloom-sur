export interface GeoJsonPoint {
  type: 'Point';
  coordinates: [number, number]; // [longitud, latitud]
}

export interface Station {
  id: string;
  lake_id: string;
  name: string;
  code: string;
  status: string; // 'active', 'inactive', etc.
  point: GeoJsonPoint;
}
