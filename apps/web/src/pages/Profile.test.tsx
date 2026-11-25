import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  getProfile: vi.fn(),
  user: null as
    | {
        email?: string;
        user_metadata?: Record<string, unknown>;
      }
    | null,
}));

vi.mock('../services/apiClient', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../services/apiClient')>();
  return {
    ...actual,
    apiClient: {
      ...actual.apiClient,
      get: mocks.getProfile,
    },
  };
});

vi.mock('../contexts/useAuth', () => ({
  useAuth: () => ({ user: mocks.user }),
}));

import Profile from './Profile';

describe('Profile', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.user = null;
  });

  afterEach(() => {
    cleanup();
  });

  it('maps current user and active membership data', async () => {
    mocks.getProfile.mockResolvedValueOnce({
      id: 'user-1',
      email: 'researcher@example.org',
      memberships: [
        {
          id: 'membership-1',
          role: 'investigador',
          status: 'active',
          organization: {
            id: 'org-1',
            name: 'Instituto de Lagos',
            status: 'active',
          },
        },
      ],
    });

    render(<Profile />);

    expect(await screen.findAllByText('Instituto de Lagos')).toHaveLength(2);
    expect(screen.getByText('researcher@example.org')).toBeInTheDocument();
    expect(screen.getByText('investigador')).toBeInTheDocument();
    expect(mocks.getProfile).toHaveBeenCalledWith('auth/me');
  });

  it('handles missing membership data and organization safely', async () => {
    mocks.user = {
      email: 'fallback@example.org',
      user_metadata: { full_name: '  Ana Ríos  ', role: 'auditor' },
    };
    mocks.getProfile.mockResolvedValueOnce({
      id: 'user-2',
      email: null,
      memberships: [{ id: 'membership-2', role: '', status: '', organization: null }],
    });

    render(<Profile />);

    expect(await screen.findByRole('heading', { name: 'Ana Ríos' })).toBeInTheDocument();
    expect(screen.getByText('fallback@example.org')).toBeInTheDocument();
    expect(screen.getAllByText('Sin organización')).toHaveLength(2);
    expect(screen.getByText('auditor')).toBeInTheDocument();
  });

  it('falls back safely when the memberships field is absent', async () => {
    mocks.getProfile.mockResolvedValueOnce({
      id: 'user-3',
      email: 'no-membership@example.org',
    });

    render(<Profile />);

    expect(await screen.findAllByText('Sin organización')).toHaveLength(2);
    expect(screen.getByText('Sin rol')).toBeInTheDocument();
  });
});
