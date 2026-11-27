import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../services/apiClient';
import { LakeDetail } from './LakeDetail';

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock('../services/apiClient', async (importOriginal) => {
  const original = await importOriginal<typeof import('../services/apiClient')>();
  return { ...original, apiClient: { get: mockGet } };
});

vi.mock('../components/Map/BaseMap', () => ({
  default: () => <div data-testid="base-map" />,
}));

describe('LakeDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('muestra el lago aunque falle la consulta de estaciones', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/stations')) {
        return Promise.reject(
          new ApiError({ message: 'Permission denied', status: 500 }),
        );
      }

      return Promise.resolve({
        id: 'lake-1',
        name: 'Lago Uno',
        region: 'Los Ríos',
        status: 'active',
        geom: null,
      });
    });

    render(
      <MemoryRouter initialEntries={['/lakes/lake-1']}>
        <Routes>
          <Route path="/lakes/:id" element={<LakeDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Lago Uno' })).toBeInTheDocument();
    expect(screen.getByText(/no se pudieron cargar las estaciones/i)).toBeInTheDocument();
  });

  it('S3-24: muestra el detalle de Panguipulli con su registro y fuente disponible', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/stations')) {
        return Promise.resolve([
          {
            id: 'st-panguipulli-1',
            lake_id: 'lake-panguipulli',
            code: 'DGA-PAN-01',
            name: 'Estación Panguipulli Centro',
            status: 'ACTIVE',
          },
        ]);
      }

      return Promise.resolve({
        id: 'lake-panguipulli',
        name: 'Panguipulli',
        region: 'Los Ríos',
        description: 'Fuente disponible: DGA / Sentinel-2.',
        status: 'ACTIVE',
        geom: null,
      });
    });

    render(
      <MemoryRouter initialEntries={['/lakes/lake-panguipulli']}>
        <Routes>
          <Route path="/lakes/:id" element={<LakeDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole('heading', { name: 'Panguipulli' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Los Ríos')).toBeInTheDocument();
    expect(screen.getByText('ID Catálogo')).toBeInTheDocument();
    expect(screen.getByText('lake-panguipulli')).toBeInTheDocument();
    expect(
      screen.getAllByText(/Fuente disponible: DGA \/ Sentinel-2\./i).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText('Estación Panguipulli Centro')).toBeInTheDocument();
    expect(screen.getByText('DGA-PAN-01')).toBeInTheDocument();
  });
});
