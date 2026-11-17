import { apiClient } from './apiClient';
import type { ModelConfig } from '../types/models';

export const modelsService = {
  /**
   * Consulta los modelos disponibles para un lago específico.
   */
  async getModelsByLake(lakeId: string): Promise<ModelConfig[]> {
    return apiClient.get<ModelConfig[]>(`models?lake_id=${lakeId}`);
  },
};
