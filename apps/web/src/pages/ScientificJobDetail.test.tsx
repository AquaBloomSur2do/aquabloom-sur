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

  it('muestra métricas MAE y RMSE, modelo baseline, versión, estado y advertencias en entrenamiento', async () => {
    vi.mocked(executionsService.getJobStatus).mockResolvedValue({
      job_id: 'job-train-161',
      job_type: 'training',
      status: 'completed',
      config: {
        dataset_id: 'dataset-1',
        version_id: 'version-2026-1',
      },
      result: {
        model: 'baseline',
        baseline: {
          strategy: 'mean_clorofila_a',
          target_variable: 'clorofila_a',
          prediction_value: 15.0,
          train_sample_count: 8,
          validation_sample_count: 2,
        },
        prediction_value: 15.0,
        predictions: [15.0, 15.0],
        metrics: {
          mae: 2.3456,
          rmse: 3.4567,
        },
        version: 'version-2026-1',
        dataset_version_id: 'version-2026-1',
        model_version_id: null,
        status: 'completed',
        warnings: [
          'Modelo baseline de referencia basado en la media de clorofila_a de entrenamiento.',
        ],
      },
      dataset_version_id: 'version-2026-1',
      model_version_id: null,
      requested_by: 'user-1',
      error_message: null,
      created_at: '2026-11-23T12:00:00Z',
      started_at: '2026-11-23T12:00:01Z',
      completed_at: '2026-11-23T12:00:02Z',
      updated_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/scientific/jobs/job-train-161']}>
        <Routes>
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('2.3456')).toBeInTheDocument();
    expect(screen.getByText('3.4567')).toBeInTheDocument();
    expect(screen.getByText(/baseline \(mean_clorofila_a\)/i)).toBeInTheDocument();
    expect(screen.getAllByText('version-2026-1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Completado').length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByText(
        'Modelo baseline de referencia basado en la media de clorofila_a de entrenamiento.'
      )
    ).toBeInTheDocument();
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

  it('muestra errores de carga y el mensaje de error del trabajo fallido', async () => {
    vi.mocked(executionsService.getJobStatus).mockRejectedValueOnce(
      new Error('No se pudo consultar el trabajo.')
    );

    const { unmount } = render(
      <MemoryRouter initialEntries={['/scientific/jobs/job-error']}>
        <Routes>
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo consultar el trabajo.'
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
      </MemoryRouter>
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Falló el procesamiento de la escena.'
    );
    expect(screen.getByText('Fallido')).toBeInTheDocument();
  });
});
