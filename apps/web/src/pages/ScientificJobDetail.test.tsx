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
      job_id: 'job-123',
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
      </MemoryRouter>,
    );

    expect(await screen.findByText('dataset-version-1')).toBeInTheDocument();
    expect(screen.getByText('model-version-1')).toBeInTheDocument();
    expect(screen.getByText('model-1')).toBeInTheDocument();
    expect(screen.getByText('scene-1')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Abrir manifiesto' }),
    ).toBeDisabled();
    expect(
      screen.getByRole('button', { name: 'Abrir artefacto' }),
    ).toBeDisabled();
    expect(executionsService.getJobStatus).toHaveBeenCalledWith(
      'job-123',
      expect.any(AbortSignal),
    );
  });

  it('indica cuando la API no entrega referencias de dataset o artefacto', async () => {
    vi.mocked(executionsService.getJobStatus).mockResolvedValue({
      job_id: 'job-456',
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
      </MemoryRouter>,
    );

    expect(await screen.findAllByText('No informada por la API')).toHaveLength(
      2,
    );
    expect(
      screen.queryByRole('button', { name: 'Abrir manifiesto' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Abrir artefacto' }),
    ).not.toBeInTheDocument();
  });

  it('muestra errores de carga y el mensaje de error del trabajo fallido', async () => {
    vi.mocked(executionsService.getJobStatus).mockRejectedValueOnce(
      new Error('No se pudo consultar el trabajo.'),
    );

    const { unmount } = render(
      <MemoryRouter initialEntries={['/scientific/jobs/job-error']}>
        <Routes>
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo consultar el trabajo.',
    );
    unmount();

    vi.mocked(executionsService.getJobStatus).mockResolvedValueOnce({
      job_id: 'job-failed',
      job_type: 'estimation',
      status: 'failed',
      config: null,
      result: null,
      dataset_version_id: null,
      model_version_id: null,
      requested_by: null,
      error_message: 'Falló el procesamiento de la escena.',
      created_at: '2026-11-20T12:00:00Z',
      started_at: null,
      completed_at: null,
      updated_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/scientific/jobs/job-failed']}>
        <Routes>
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Falló el procesamiento de la escena.',
    );
    expect(screen.getByText('Fallido')).toBeInTheDocument();
  });

  it('consulta periódicamente el estado del worker hasta mostrar el resultado persistido', async () => {
    vi.mocked(executionsService.getJobStatus)
      .mockResolvedValueOnce({
        job_id: 'job-staging-1',
        job_type: 'training',
        status: 'queued',
        config: { dataset_id: 'ds-1', version_id: 'ver-1' },
        result: null,
        dataset_version_id: null,
        model_version_id: null,
        requested_by: 'user-1',
        error_message: null,
        created_at: '2026-11-22T12:00:00Z',
        started_at: null,
        completed_at: null,
        updated_at: null,
      })
      .mockResolvedValueOnce({
        job_id: 'job-staging-1',
        job_type: 'training',
        status: 'running',
        config: { dataset_id: 'ds-1', version_id: 'ver-1' },
        result: null,
        dataset_version_id: null,
        model_version_id: null,
        requested_by: 'user-1',
        error_message: null,
        created_at: '2026-11-22T12:00:00Z',
        started_at: '2026-11-22T12:00:01Z',
        completed_at: null,
        updated_at: null,
      })
      .mockResolvedValueOnce({
        job_id: 'job-staging-1',
        job_type: 'training',
        status: 'completed',
        config: { dataset_id: 'ds-1', version_id: 'ver-1' },
        result: {
          prediction_value: 15.0,
          predictions: [15.0],
          metrics: { mae: 15.0, rmse: 15.0 },
        },
        dataset_version_id: null,
        model_version_id: null,
        requested_by: 'user-1',
        error_message: null,
        created_at: '2026-11-22T12:00:00Z',
        started_at: '2026-11-22T12:00:01Z',
        completed_at: '2026-11-22T12:00:02Z',
        updated_at: '2026-11-22T12:00:02Z',
      });

    render(
      <MemoryRouter initialEntries={['/scientific/jobs/job-staging-1']}>
        <Routes>
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail pollIntervalMs={10} />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Modelo baseline')).toBeInTheDocument();
    expect(screen.getAllByText('Completado').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('MAE')).toBeInTheDocument();
    expect(screen.getByText('RMSE')).toBeInTheDocument();
    expect(screen.getByText('Predicción baseline')).toBeInTheDocument();
    expect(screen.getAllByText('15').length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText('ver-1').length).toBeGreaterThanOrEqual(1);
    expect(executionsService.getJobStatus).toHaveBeenCalledTimes(3);
  });
});





