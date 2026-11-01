import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../services/apiClient';
import { DatasetReview } from './DatasetReview';

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
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
    apiClient: { get: mockGet, post: mockPost },
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
  version_id: 'version-1',
  manifest_id: 'manifest-1',
  variables: ['temperatura', 'clorofila_a', 'turbidez', 'ph'],
  checksum: 'a'.repeat(64),
  download_url: '/api/v1/datasets/versions/version-1/training-file/download',
  manifest_version: '1.0.0',
  sources: ['sensor-telemetry-primary'],
  is_experimental: true,
  is_synthetic: true,
};

describe('DatasetReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((url: string) => {
      if (url === 'datasets/review') {
        return Promise.resolve(reviewDatasets);
      }
      if (url.includes('/training-file')) {
        return Promise.resolve(mockManifest);
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('muestra la información del manifiesto y sus advertencias experimentales/sintéticas', async () => {
    render(<DatasetReview />);

    expect(
      await screen.findByText('Manifiesto de Entrenamiento')
    ).toBeInTheDocument();
    expect(await screen.findByText(/1\.0\.0/)).toBeInTheDocument();
    expect(
      await screen.findByText('sensor-telemetry-primary')
    ).toBeInTheDocument();
    expect(screen.getByText(/Aviso Experimental/i)).toBeInTheDocument();
    expect(screen.getByText(/Aviso Sintético/i)).toBeInTheDocument();
  });

  it('diferencia visualmente el estado de revisión técnica de la publicación oficial', async () => {
    render(<DatasetReview />);

    expect(
      await screen.findByText('Aprobado en revisión técnica (No publicado)')
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No publicado \(pendiente de publicación\)/i)
    ).toBeInTheDocument();
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

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Respuesta guardada: Rechazada.'
    );
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
});

