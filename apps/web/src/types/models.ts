export interface ModelConfig {
  id: string;
  name: string;
  version: string;
  target_variable: string;
  unit: string;
  required_index: string;
  status: 'EXPERIMENTAL' | 'VALIDATED' | 'DEPRECATED' | 'REJECTED';
  min_index_value?: number;
  max_index_value?: number;
  created_at: string;
}

export interface EstimationConfig {
  model_id: string;
  scene_id: string;
}
