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
  memberships: DatasetSceneMembership[];
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
