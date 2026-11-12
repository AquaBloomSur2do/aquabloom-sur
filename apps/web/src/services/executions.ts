import { apiClient } from './apiClient';

export interface JobCreatePayload {
  dataset_version_id: string;
  job_type: 'TRAINING' | 'ESTIMATION';
  config: Record<string, unknown>;
}

export interface JobResponse {
  job_id: string;
  status: string;
  message?: string;
}

export const executionsService = {
  /**
   * Envía la solicitud para iniciar un trabajo asíncrono científico (S2-163).
   */
  async createJob(payload: JobCreatePayload): Promise<JobResponse> {
    return apiClient.post<JobResponse>('executions/jobs', payload);
  },

  /**
   * Consulta el estado actual de un trabajo científico en proceso.
   */
  async getJobStatus(jobId: string): Promise<JobResponse> {
    return apiClient.get<JobResponse>(`executions/jobs/${jobId}`);
  },
};
