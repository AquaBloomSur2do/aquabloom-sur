import { apiClient } from './apiClient';

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

export interface JobStatusResponse {
  id: string;
  job_type: 'training' | 'modeling' | 'estimation';
  status: 'queued' | 'running' | 'completed' | 'failed';
  config: Record<string, unknown>;
  result: Record<string, unknown> | null;
  dataset_version_id: string | null;
  model_version_id: string | null;
  requested_by: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
}

export const executionsService = {
  /**
   * Envía la solicitud para iniciar un trabajo asíncrono científico (S2-163 / S2-175).
   */
  async createJob(payload: JobCreatePayload): Promise<JobResponse> {
    return apiClient.post<JobResponse>('executions/jobs', payload);
  },

  /**
   * Consulta el estado actual de un trabajo científico en proceso.
   */
  async getJobStatus(
    jobId: string,
    signal?: AbortSignal
  ): Promise<JobStatusResponse> {
    return apiClient.get<JobStatusResponse>(`executions/${jobId}`, { signal });
  },
};
