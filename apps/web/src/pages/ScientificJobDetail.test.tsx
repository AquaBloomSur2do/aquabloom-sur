import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { executionsService } from '../services/executions';
import { ScientificJobDetail } from './ScientificJobDetail';

vi.mock('../services/executions', () => ({
  executionsService: {
    getJobStatus: vi.fn(),
  },
}));

describe('ScientificJobDetail', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('muestra la trazabilidad disponible y mantiene deshabilitados los enlaces incompletos', async () => {
    vi.mocked(executionsService.getJobStatus).mockResolvedValue({
      id: 'job-123',
      job_type: 'estimation',
      status: 'completed',
      config: { model_id: 'model-1', scene_id: 'scene-1' },
      result: { accuracy: 0.98 },
      dataset_version_id: 'dataset-version-1',
      model_version_id: 'model-version-1',
      requested_by: 'user-1',
      error_message: null,
      created_at: '2026-11-20T12:00:00Z',
      started_at: null,
      completed_at: null,
      updated_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/scientific/jobs/job-123']}>
        <Routes>
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('dataset-version-1')).toBeInTheDocument();
    expect(screen.getByText('model-version-1')).toBeInTheDocument();
    expect(screen.getByText('model-1')).toBeInTheDocument();
    expect(screen.getByText('scene-1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Abrir manifiesto' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Abrir artefacto' })).toBeDisabled();
    expect(executionsService.getJobStatus).toHaveBeenCalledWith(
      'job-123',
      expect.any(AbortSignal)
    );
  });

  it('indica cuando la API no entrega referencias de dataset o artefacto', async () => {
    vi.mocked(executionsService.getJobStatus).mockResolvedValue({
      id: 'job-456',
      job_type: 'estimation',
      status: 'queued',
      config: {},
      result: null,
      dataset_version_id: null,
      model_version_id: null,
      requested_by: null,
      error_message: null,
      created_at: '2026-11-20T12:00:00Z',
      started_at: null,
      completed_at: null,
      updated_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/scientific/jobs/job-456']}>
        <Routes>
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(
      await screen.findAllByText('No informada por la API')
    ).toHaveLength(2);
    expect(
      screen.queryByRole('button', { name: 'Abrir manifiesto' })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Abrir artefacto' })
    ).not.toBeInTheDocument();
  });
});
