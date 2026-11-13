import { apiClient } from './apiClient';
import type { ModelConfig, EstimationConfig, JobResponse } from '../types/models';

export const modelsService = {
  /**
   * Consulta los modelos disponibles para un lago específico.
   * Filtra opcionalmente por estado (ej. EXPERIMENTAL o VALIDATED).
   */
  async getModelsByLake(lakeId: string): Promise<ModelConfig[]> {
    return apiClient.get<ModelConfig[]>(`models?lake_id=${lakeId}`);
  },

  /**
   * Inicia un trabajo de estimación asíncrono vinculando el modelo y la escena.
   */
  async createEstimationJob(payload: EstimationConfig): Promise<JobResponse> {
    return apiClient.post<JobResponse>('estimations', payload);
  }
};
