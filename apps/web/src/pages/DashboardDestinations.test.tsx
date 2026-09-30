import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Dashboard } from './Dashboard';
import { LakesList } from './LakesList';
import { StationsList } from './StationsList';

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock('../services/apiClient', () => ({
  apiClient: { get: mockGet },
}));

vi.mock('../contexts/useAuth', () => ({
  useAuth: () => ({
    user: { app_metadata: {}, user_metadata: { role: 'administrador' } },
  }),
}));

describe('Dashboard destinations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('sends each dashboard card to its matching page', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: /ver lagos/i })).toHaveAttribute(
      'href',
      '/lakes',
    );
    expect(
      screen.getByRole('link', { name: /ver estaciones/i }),
    ).toHaveAttribute('href', '/stations');
    expect(
      screen.getByRole('link', { name: /ir al catálogo/i }),
    ).toHaveAttribute('href', '/lakes');
  });

  it('muestra el acceso al formulario de creación desde el catálogo', () => {
    render(
      <MemoryRouter>
        <LakesList />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: /registrar lago/i })).toHaveAttribute(
      'href',
      '/lakes/new',
    );
  });

  it('muestra estaciones activas junto al lago correspondiente', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === 'lakes?status=active&limit=100') {
        return Promise.resolve({
          items: [{ id: 'lake-1', name: 'Lago Uno', region: 'Los Ríos' }],
        });
      }
      return Promise.resolve([
        {
          id: 'station-1',
          lake_id: 'lake-1',
          code: 'EST-01',
          name: 'Estación Centro',
          status: 'active',
        },
      ]);
    });

    render(
      <MemoryRouter>
        <StationsList />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Estación Centro')).toBeInTheDocument();
    expect(screen.getByText('Lago Uno')).toBeInTheDocument();
  });

});