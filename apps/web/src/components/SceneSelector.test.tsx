import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../services/apiClient';
import { SceneSelector } from './SceneSelector';

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      signOut: vi.fn(),
    },
  },
}));

vi.mock('../services/apiClient', async (importOriginal) => {
  const original = await importOriginal<typeof import('../services/apiClient')>();
  return { ...original, apiClient: { ...original.apiClient, get: vi.fn() } };
});

const scene = {
  id: 'scene-1',
  lake_id: 'lake-1',
  scene_identifier: 'S2A_20260320',
  acquisition_date: '2026-03-20',
  created_at: '2026-03-20T10:00:00Z',
};

describe('SceneSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('filters registered scenes and allows selecting one', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      items: [scene],
      page: 1,
      page_size: 20,
      total: 1,
    });

    render(<SceneSelector lakeId="lake-1" />);
    fireEvent.change(screen.getByLabelText('Desde'), {
      target: { value: '2026-03-01' },
    });
    fireEvent.change(screen.getByLabelText('Hasta'), {
      target: { value: '2026-03-31' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar escenas' }));

    expect(await screen.findByText('S2A_20260320')).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith(
      'lakes/lake-1/scenes?start_date=2026-03-01&end_date=2026-03-31&page=1&page_size=20',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );

    fireEvent.click(
      screen.getByRole('radio', { name: 'Seleccionar escena S2A_20260320' })
    );
    expect(
      screen.getByText('Escena seleccionada: S2A_20260320 (2026-03-20)')
    ).toBeInTheDocument();
  });

  it('rejects reversed dates without calling the API', async () => {
    render(<SceneSelector lakeId="lake-1" />);
    fireEvent.change(screen.getByLabelText('Desde'), {
      target: { value: '2026-03-31' },
    });
    fireEvent.change(screen.getByLabelText('Hasta'), {
      target: { value: '2026-03-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar escenas' }));

    expect(
      await screen.findByRole('alert')
    ).toHaveTextContent('La fecha inicial debe ser anterior o igual a la fecha final.');
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it('surfaces API errors and lets the user retry', async () => {
    vi.mocked(apiClient.get)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        items: [scene],
        page: 1,
        page_size: 20,
        total: 1,
      });

    render(<SceneSelector lakeId="lake-1" />);
    fireEvent.change(screen.getByLabelText('Desde'), {
      target: { value: '2026-03-01' },
    });
    fireEvent.change(screen.getByLabelText('Hasta'), {
      target: { value: '2026-03-31' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar escenas' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudieron cargar las escenas registradas.'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    await waitFor(() => {
      expect(screen.getByText('S2A_20260320')).toBeInTheDocument();
    });
  });
});
