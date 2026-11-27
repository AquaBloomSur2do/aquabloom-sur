import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LakesList } from './LakesList';
import { apiClient } from '../services/apiClient';

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

vi.mock('../contexts/useAuth', () => ({
  useAuth: () => ({
    user: {
      app_metadata: { role: 'administrador' },
      user_metadata: { role: 'administrador' },
    },
  }),
}));

afterEach(cleanup);

describe('LakesList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra Panguipulli con un acceso al detalle', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce([
      {
        id: 'lake-panguipulli',
        name: 'Panguipulli',
        region: 'Los Ríos',
        status: 'active',
        station_count: 2,
      },
    ]);

    render(
      <MemoryRouter>
        <LakesList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Panguipulli')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Ver detalle del lago Panguipulli' })).toBeInTheDocument();
  });
});
