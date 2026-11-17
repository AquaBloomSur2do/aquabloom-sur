export type DatasetDecisionValue = 'accepted' | 'rejected';

export interface DatasetDecision {
  id: string;
  membership_id: string;
  decision: DatasetDecisionValue;
  reason: string | null;
  decided_by: string | null;
  decided_at: string;
}

export interface DatasetSceneMembership {
  id: string;
  version_id: string;
  scene_provider: string;
  scene_external_id: string;
  added_at: string;
  decisions: DatasetDecision[];
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version_number: number;
  state?: string;
  status: string;
  created_at: string;
  published_at?: string | null;
  memberships: DatasetSceneMembership[];
}

export interface DatasetVersionPublication {
  id: string;
  dataset_id: string;
  version_number: number;
  status: 'draft' | 'published' | 'archived';
  created_at: string;
  published_at: string | null;
}

export interface ReviewDataset {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  created_at: string;
  versions: DatasetVersion[];
}

export interface DatasetDecisionInput {
  decision: DatasetDecisionValue;
  reason: string;
}

export interface DatasetCandidate {
  id: string;
  lake_id: string;
  data_uri: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  submitted_at: string;
  exclusion_reason?: string; // Motivo de exclusión si aplica
  source_provider?: string;  // Procedencia
}

export interface ManifestItem {
  id: string;
  source_name?: string | null;
  checksum: string;
  is_synthetic?: boolean;
  is_experimental?: boolean;
}

export interface ManifestRule {
  id: string;
  description: string;
  checksum: string;
}

export interface DatasetManifest {
  dataset_id: string;
  version_id: string;
  version_number: string;
  records: ManifestItem[];
  sources: ManifestItem[];
  observations: ManifestItem[];
  rules: ManifestRule[];
  manifest_checksum: string;
  global_checksum?: string;
}
