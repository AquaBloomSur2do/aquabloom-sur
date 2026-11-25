import { apiClient } from './apiClient';

const ACTIVE_ORG_STORAGE_KEY = 'aquabloom:active_organization_id';

export interface JobCreatePayload {
  dataset_version_id?: string;
  job_type: 'TRAINING' | 'ESTIMATION';
  config: Record<string, unknown>;
}

export interface JobResponse {
  job_id: string;
  status: string;
  status_url?: string;
  message?: string;
}

export interface TrainingMetrics {
  mae: number;
  rmse: number;
}

export interface BaselineInfo {
  strategy: string;
  target_variable: string;
  prediction_value: number;
  train_sample_count: number;
  validation_sample_count: number;
}

export interface PointPredictionItem {
  point_id?: string;
  station_name?: string | null;
  station_code?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  predicted_value?: number | null;
  value?: number | null;
  unit?: string | null;
  warning?: string | null;
  warnings?: string[];
}

export interface TrainingJobResult {
  model?: string;
  model_name?: string | null;
  training_job_id?: string | null;
  dataset_id?: string | null;
  model_artifact?: {
    job_id?: string | null;
    checksum?: string | null;
    storage_path?: string | null;
  } | null;
  baseline?: BaselineInfo;
  prediction_value?: number;
  predictions?: number[] | PointPredictionItem[];
  metrics?: TrainingMetrics;
  version?: string | null;
  dataset_version_id?: string | null;
  model_version_id?: string | null;
  unit?: string | null;
  point_count?: number;
  model_id?: string;
  artifact_checksum?: string;
  status?: 'queued' | 'running' | 'completed' | 'failed' | string;
  warnings?: string[];
  [key: string]: unknown;
}

export interface JobStatusResponse {
  job_id: string;
  id?: string;
  job_type: 'training' | 'modeling' | 'estimation';
  status: 'queued' | 'running' | 'completed' | 'failed';
  config: Record<string, unknown> | null;
  result: TrainingJobResult | null;
  dataset_version_id: string | null;
  model_version_id: string | null;
  requested_by: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
}

export function setActiveOrganizationId(organizationId: string): void {
  const normalized = organizationId.trim();
  if (!normalized) return;
  try {
    window.sessionStorage.setItem(ACTIVE_ORG_STORAGE_KEY, normalized);
  } catch {
    // Ignorar restricciones de almacenamiento en entornos sin sessionStorage.
  }
}

async function resolveOrganizationId(
  signal?: AbortSignal,
): Promise<string | null> {
  try {
    const cached = window.sessionStorage.getItem(ACTIVE_ORG_STORAGE_KEY);
    if (cached) return cached;
  } catch {
    // Continuar con resolución desde la API si sessionStorage no está disponible.
  }

  try {
    const organizations = await apiClient.get<Array<{ id: string }>>(
      'organizations/',
      { signal },
    );
    const firstId = Array.isArray(organizations)
      ? (organizations[0]?.id ?? null)
      : null;
    if (firstId) {
      setActiveOrganizationId(firstId);
    }
    return firstId;
  } catch {
    return null;
  }
}

export const executionsService = {
  /**
   * Envía la solicitud para iniciar un trabajo asíncrono científico (S2-163 / S2-168 / S2-175).
   */
  async createJob(payload: JobCreatePayload): Promise<JobResponse> {
    const organizationId = await resolveOrganizationId();
    const headers = organizationId
      ? { 'X-Organization-ID': organizationId }
      : undefined;
    return apiClient.post<JobResponse>('executions/jobs', payload, { headers });
  },

  /**
   * Consulta el estado actual de un trabajo científico en proceso.
   */
  async getJobStatus(
    jobId: string,
    signal?: AbortSignal,
  ): Promise<JobStatusResponse> {
    const organizationId = await resolveOrganizationId(signal);
    const headers = organizationId
      ? { 'X-Organization-ID': organizationId }
      : undefined;
    return apiClient.get<JobStatusResponse>(`executions/${jobId}`, {
      signal,
      headers,
    });
  },
};
