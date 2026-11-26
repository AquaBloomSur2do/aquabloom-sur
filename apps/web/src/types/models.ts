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
  model_version_id?: string | null;
  training_job_id?: string | null;
  dataset_id?: string | null;
  dataset_version_id?: string | null;
  created_at: string;
}

export interface EstimationConfig {
  model_id: string;
  scene_id: string;
  model_name?: string;
  model_version_id?: string;
  training_job_id?: string;
  dataset_id?: string;
  dataset_version_id?: string;
}
