import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../services/apiClient';
import { DatasetReview } from './DatasetReview';

const { mockGet, mockPost, mockPublishVersion } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPublishVersion: vi.fn(),
}));

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      signOut: vi.fn(),
    },
  },
}));

vi.mock('../services/apiClient', async (importOriginal) => {
  const original =
    await importOriginal<typeof import('../services/apiClient')>();
  return {
    ...original,
    apiClient: {
      get: mockGet,
      post: mockPost,
      publishDatasetVersion: mockPublishVersion,
    },
  };
});

const reviewDatasets = [
  {
    id: 'dataset-1',
    organization_id: 'organization-1',
    name: 'Dataset piloto',
    description: null,
    created_at: '2026-10-27T00:00:00Z',
    versions: [
      {
        id: 'version-1',
        dataset_id: 'dataset-1',
        version_number: 1,
        state: 'APPROVED',
        status: 'APPROVED',
        created_at: '2026-10-27T00:00:00Z',
        memberships: [
          {
            id: 'membership-1',
            version_id: 'version-1',
            scene_provider: 'sentinel',
            scene_external_id: 'scene-pilot',
            added_at: '2026-10-27T00:00:00Z',
            decisions: [],
          },
        ],
      },
    ],
  },
];

const mockManifest = {
  version_number: '1',
  version_id: 'version-1',
  global_checksum: 'abc123def456',
  sources: [
    {
      id: 'source-1',
      source_name: 'Fuente Sintética',
      checksum: 'xyz789',
      is_synthetic: true,
      is_experimental: false,
    },
    {
      id: 'source-2',
      source_name: 'Fuente Real',
      checksum: 'abc999',
      is_synthetic: false,
      is_experimental: false,
    },
    {
      id: 'source-3',
      source_name: 'Fuente Experimental',
      checksum: 'exp123',
      is_synthetic: false,
      is_experimental: true,
    },
  ],
  records: [],
  observations: [],
  rules: [],
  manifest_checksum: 'global-hash-123',
};

describe('DatasetReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((url: string) => {
      if (url.includes('manifest')) {
        return Promise.resolve(mockManifest);
      }
      if (url.includes('datasets/candidates')) {
        return Promise.resolve([]);
      }
      if (url === 'lakes') {
        return Promise.resolve({ items: [] });
      }
      return Promise.resolve(reviewDatasets);
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('diferencia visualmente el estado de revisión técnica de la publicación oficial', async () => {
    render(<DatasetReview />);
    
    expect(await screen.findByText('Aprobado en revisión técnica (No publicado)')).toBeInTheDocument();
    expect(screen.getByText(/No publicado \(pendiente de publicación\)/i)).toBeInTheDocument();
  });

  it('envía la decisión y el motivo y muestra la respuesta guardada', async () => {
    mockPost.mockResolvedValue({
      id: 'decision-1',
      membership_id: 'membership-1',
      decision: 'rejected',
      reason: 'Nubes densas',
      decided_by: 'user-1',
      decided_at: '2026-10-27T00:00:00Z',
    });

    render(<DatasetReview />);

    expect(await screen.findByText('scene-pilot')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Decisión para scene-pilot'), {
      target: { value: 'rejected' },
    });
    fireEvent.change(screen.getByLabelText('Motivo para scene-pilot'), {
      target: { value: 'Nubes densas' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar decisión' }));

    expect(
      await screen.findByText('Respuesta guardada: Rechazada.')
    ).toBeInTheDocument();
    expect(mockPost).toHaveBeenCalledWith(
      'datasets/memberships/membership-1/decisions',
      { decision: 'rejected', reason: 'Nubes densas' }
    );
  });

  it('muestra explícitamente el error cuando el usuario no tiene permiso', async () => {
    mockPost.mockRejectedValue(
      new ApiError({
        message: 'Forbidden',
        status: 403,
        code: 'FORBIDDEN',
      })
    );

    render(<DatasetReview />);

    await screen.findByText('scene-pilot');
    fireEvent.change(screen.getByLabelText('Motivo para scene-pilot'), {
      target: { value: 'Escena válida' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar decisión' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permisos para registrar decisiones en este dataset.'
    );
  });

  it('publica la versión seleccionada y muestra el identificador de respuesta', async () => {
    mockPublishVersion.mockImplementation(async (versionId: string) => ({
      id: versionId,
      dataset_id: 'dataset-1',
      version_number: 1,
      status: 'published',
      created_at: '2026-10-27T00:00:00Z',
      published_at: '2026-10-29T00:00:00Z',
    }));

    render(<DatasetReview />);

    await screen.findByText('scene-pilot');
    fireEvent.click(screen.getByRole('button', { name: 'Publicar versión' }));

    expect(
      await screen.findByText('Versión publicada. ID: version-1')
    ).toBeInTheDocument();
    expect(mockPublishVersion).toHaveBeenCalledWith('version-1');
    expect(
      screen.getByRole('button', { name: 'Versión publicada' })
    ).toBeDisabled();
  });

  it('consulta y muestra los datos del manifiesto incluyendo advertencias y estados no informados', async () => {
    render(<DatasetReview />);
    
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(
        expect.stringContaining('datasets/dataset-1/versions/version-1/manifest'),
        expect.any(Object)
      );
    });

    expect(await screen.findByText(/Versión: 1/i)).toBeInTheDocument();
    
    expect(screen.getByText(/abc123def456/i)).toBeInTheDocument();
    
    expect(screen.getByText(/Fuente Sintética/i)).toBeInTheDocument();
    expect(screen.getByText(/xyz789/i)).toBeInTheDocument();
    expect(screen.getByText(/Sintético/i)).toBeInTheDocument();
    expect(screen.getByText(/Fuente Experimental/i)).toBeInTheDocument();
    expect(screen.getByText('Experimental', { exact: true })).toBeInTheDocument();

    expect(screen.getByText(/Condición no informada/i)).toBeInTheDocument();
  });

  it('S3-47: filtra Panguipulli y solo muestra recursos visibles vinculados a ese lago', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('manifest')) {
        return Promise.resolve(mockManifest);
      }
      if (url.includes('datasets/candidates')) {
        return Promise.resolve([
          {
            id: 'candidate-panguipulli-approved',
            lake_id: 'lake-panguipulli',
            data_uri: 's3://ingest/panguipulli-visible.csv',
            status: 'APPROVED',
            submitted_at: '2026-10-27T00:00:00Z',
          },
          {
            id: 'candidate-panguipulli-pending',
            lake_id: 'lake-panguipulli',
            data_uri: 's3://ingest/panguipulli-pending.csv',
            status: 'PENDING',
            submitted_at: '2026-10-27T00:00:00Z',
          },
          {
            id: 'candidate-villarrica-approved',
            lake_id: 'lake-villarrica',
            data_uri: 's3://ingest/villarrica-visible.csv',
            status: 'APPROVED',
            submitted_at: '2026-10-27T00:00:00Z',
          },
          {
            id: 'candidate-inactive-lake-approved',
            lake_id: 'lake-hidden',
            data_uri: 's3://ingest/inactive-lake.csv',
            status: 'APPROVED',
            submitted_at: '2026-10-27T00:00:00Z',
          },
        ]);
      }
      if (url === 'lakes') {
        return Promise.resolve({
          items: [
            { id: 'lake-panguipulli', name: 'Panguipulli', status: 'active' },
            { id: 'lake-villarrica', name: 'Villarrica', status: 'active' },
            { id: 'lake-hidden', name: 'Lago no disponible', status: 'inactive' },
          ],
        });
      }
      return Promise.resolve(reviewDatasets);
    });

    render(<DatasetReview />);

    await screen.findByRole('option', { name: 'Panguipulli' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar candidatos por lago' }), {
      target: { value: 'lake-panguipulli' },
    });

    expect(
      await screen.findByText('s3://ingest/panguipulli-visible.csv')
    ).toBeInTheDocument();
    expect(
      screen.queryByText('s3://ingest/panguipulli-pending.csv')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('s3://ingest/villarrica-visible.csv')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('s3://ingest/inactive-lake.csv')
    ).not.toBeInTheDocument();
  });

  it('muestra el estado vacío cuando Panguipulli no tiene recursos visibles vinculados', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('manifest')) {
        return Promise.resolve(mockManifest);
      }
      if (url.includes('datasets/candidates')) {
        return Promise.resolve([
          {
            id: 'candidate-panguipulli-pending',
            lake_id: 'lake-panguipulli',
            data_uri: 's3://ingest/panguipulli-pending.csv',
            status: 'PENDING',
            submitted_at: '2026-10-27T00:00:00Z',
          },
        ]);
      }
      if (url === 'lakes') {
        return Promise.resolve({
          items: [
            { id: 'lake-panguipulli', name: 'Panguipulli', status: 'active' },
          ],
        });
      }
      return Promise.resolve(reviewDatasets);
    });

    render(<DatasetReview />);

    await screen.findByRole('option', { name: 'Panguipulli' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar candidatos por lago' }), {
      target: { value: 'lake-panguipulli' },
    });

    expect(
      await screen.findByRole('status')
    ).toHaveTextContent('No hay recursos visibles vinculados a Panguipulli.');
    expect(
      screen.queryByText('s3://ingest/panguipulli-pending.csv')
    ).not.toBeInTheDocument();
  });
});
