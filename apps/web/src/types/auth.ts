export interface Profile {
  id: string;
  auth_id: string;
  name: string;
  status: 'ACTIVE' | 'INACTIVE';
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  status: 'ACTIVE' | 'INACTIVE';
  created_at: string;
  updated_at: string;
}

export interface Membership {
  id: string;
  profile_id: string;
  organization_id: string;
  role: 'visitor' | 'researcher' | 'curator' | 'administrator';
  status: string;
}

export interface AuthMeResponse {
  profile: Profile;
  organizations: Organization[];
  memberships: Membership[];
  permissions: string[];
}
