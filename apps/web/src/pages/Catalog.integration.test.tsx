import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../services/apiClient';
import Catalog from './Catalog';

const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn(),
}));

vi.mock('../components/Map/BaseMap', () => ({
  default: () => <div data-testid="base-map" />,
}));

vi.mock('../services/apiClient', async (importOriginal) => {
  const original =
    await importOriginal<typeof import('../services/apiClient')>();
  return {
    ...original,
    default: {
      ...original.default,
      get: mockGet,
    },
  };
});

const validResponse = {
  items: [
    {
      id: 'lake-1',
      name: 'Lago Villarrica',
      region: 'La Araucanía',
      status: 'Active',
    },
  ],
  page: 1,
  page_size: 10,
  total: 1,
};

const emptyResponse = {
  items: [],
  page: 1,
  page_size: 10,
  total: 0,
};

const refreshedValidResponse = {
  items: [
    {
      id: 'lake-2',
      name: 'Lago Ranco',
      region: 'Los Ríos',
      status: 'Active',
    },
  ],
  page: 1,
  page_size: 10,
  total: 1,
};

const forbiddenError = new ApiError({
  message: 'Forbidden',
  status: 403,
  code: 'FORBIDDEN',
});

function getRegionFromRequest(url: string): string | null {
  return new URL(url, 'http://localhost').searchParams.get('region');
}

function renderCatalog() {
  return render(
    <MemoryRouter>
      <Catalog />
    </MemoryRouter>
  );
}

function selectRegion(region: string) {
  fireEvent.change(screen.getByLabelText('Filtrar por región'), {
    target: { value: region },
  });
}

describe('Integración de la consulta web del catálogo (S3-40 / AQU-384)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((url: string) => {
      const region = getRegionFromRequest(url);
      if (region === 'La Araucanía') {
        return Promise.reject(forbiddenError);
      }
      if (region === 'Los Lagos') {
        return Promise.resolve(emptyResponse);
      }
      if (region === 'Los Ríos') {
        return Promise.resolve(refreshedValidResponse);
      }
      return Promise.resolve(validResponse);
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('mantiene separados el resultado válido, el acceso denegado y el estado vacío sin residuos visuales', async () => {
    renderCatalog();

    expect(await screen.findByText('Lago Villarrica')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Ver Detalles' })
    ).toBeInTheDocument();
    expect(screen.queryByText('Lago Ranco')).not.toBeInTheDocument();
    expect(screen.queryByText('Catálogo Vacío')).not.toBeInTheDocument();
    expect(screen.queryByText('Acceso denegado')).not.toBeInTheDocument();
    expect(screen.queryByText('Error de Conexión')).not.toBeInTheDocument();

    selectRegion('La Araucanía');

    expect(await screen.findByText('Acceso denegado')).toBeInTheDocument();
    expect(
      screen.getByText('No tienes permisos para consultar el catálogo de lagos.')
    ).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Acceso denegado');
    expect(screen.queryByText('Lago Villarrica')).not.toBeInTheDocument();
    expect(screen.queryByText('Lago Ranco')).not.toBeInTheDocument();
    expect(screen.queryByText('Catálogo Vacío')).not.toBeInTheDocument();
    expect(screen.queryByText('Error de Conexión')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /reintentar/i })
    ).not.toBeInTheDocument();

    selectRegion('Los Lagos');

    expect(await screen.findByText('Catálogo Vacío')).toBeInTheDocument();
    expect(
      screen.getByText('No se encontraron registros para los filtros aplicados.')
    ).toBeInTheDocument();
    expect(screen.queryByText('Acceso denegado')).not.toBeInTheDocument();
    expect(screen.queryByText('Lago Villarrica')).not.toBeInTheDocument();
    expect(screen.queryByText('Lago Ranco')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    selectRegion('Los Ríos');

    expect(await screen.findByText('Lago Ranco')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Ver Detalles' })
    ).toBeInTheDocument();
    expect(screen.queryByText('Lago Villarrica')).not.toBeInTheDocument();
    expect(screen.queryByText('Catálogo Vacío')).not.toBeInTheDocument();
    expect(screen.queryByText('Acceso denegado')).not.toBeInTheDocument();
    expect(screen.queryByText('Error de Conexión')).not.toBeInTheDocument();

    expect(mockGet).toHaveBeenCalledTimes(4);
    expect(getRegionFromRequest(mockGet.mock.calls[0][0])).toBeNull();
    expect(getRegionFromRequest(mockGet.mock.calls[1][0])).toBe('La Araucanía');
    expect(getRegionFromRequest(mockGet.mock.calls[2][0])).toBe('Los Lagos');
    expect(getRegionFromRequest(mockGet.mock.calls[3][0])).toBe('Los Ríos');
  });
});