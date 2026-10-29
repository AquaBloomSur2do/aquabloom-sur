// apps/web/src/types/satellite.ts

/**
 * Representa el estado de procesamiento o calidad de una escena satelital
 */
export type SceneQuality = 'VALID' | 'CLOUDY' | 'INVALID' | 'PROCESSING';

/**
 * Representa una escena satelital (S2A/S2B L2A) persistida en el sistema
 */
export interface SatelliteScene {
  id: string;
  lake_id: string;
  scene_identifier: string;
  acquisition_date: string;          // Fecha de captura (ISO 8601 UTC)
  cloud_cover_percentage: number;
  quality_status: SceneQuality;
  metadata: Record<string, unknown>; // Cambio: unknown en vez de any
  file_references: Record<string, unknown>[]; // Cambio: unknown en vez de any
  created_at: string;
}

/**
 * Esquema de respuesta paginada al listar escenas en el catálogo
 */
export interface SceneListResponse {
  items: SatelliteScene[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Esquema para registrar una nueva escena
 */
export interface SceneCreateRequest {
  lake_id: string;
  scene_identifier: string;
  acquisition_date: string;
  cloud_cover_percentage: number;
  metadata?: Record<string, unknown>; // Cambio: unknown en vez de any
  file_references?: Record<string, unknown>[]; // Cambio: unknown en vez de any
}

/**
 * Parámetros para buscar y filtrar escenas (Query Params)
 */
export interface SceneQueryParams {
  lake_id?: string;
  start_date?: string;
  end_date?: string;
  max_cloud_cover?: number;
  page?: number;
  page_size?: number;
}