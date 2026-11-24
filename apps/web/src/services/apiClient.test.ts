import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test-access-token' } },
      }),
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

  it('publishes a dataset version through the authorized API endpoint', async () => {
    const publishedVersion = {
      id: 'version-1',
      dataset_id: 'dataset-1',
      version_number: 1,
      status: 'published',
      created_at: '2026-10-27T00:00:00Z',
      published_at: '2026-10-29T00:00:00Z',
    };
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(publishedVersion), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const { apiClient } = await import('./apiClient');

    const result = await apiClient.publishDatasetVersion('version-1');

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/datasets/versions/version-1/publish',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer test-access-token',
        }),
      }),
    );
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.body).toBeUndefined();
    expect(result).toEqual(publishedVersion);
  });
});
