import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      signOut: vi.fn(),
    },
  },
}));

describe('apiClient', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000/api/v1/');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        text: async () => '{}',
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('preserves the HTTP protocol and normalizes trailing slashes', async () => {
    const { apiClient } = await import('./apiClient');

    await apiClient.get('lakes');

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/lakes',
      expect.objectContaining({ method: 'GET' }),
    );
  });
});