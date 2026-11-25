import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ScientificJobDetail } from '../pages/ScientificJobDetail';
import { executionsService } from '../services/executions';
import { modelsService } from '../services/models';
import { EstimationForm } from './EstimationForm';

vi.mock('../services/models', () => ({
  modelsService: {
    getModelsByLake: vi.fn(),
  },
}));

vi.mock('../services/executions', () => ({
  executionsService: {
    createJob: vi.fn(),
    getJobStatus: vi.fn(),
  },
}));

vi.mock('../services/apiClient', () => ({
  ApiError: class ApiError extends Error {},
}));

const MODEL_VERSION_ID = '88888888-8888-4888-8888-888888888888';
const SCENE_ID = '44444444-4444-4444-8444-444444444444';
const JOB_ID = '99999999-9999-4999-8999-999999999999';

describe('flujo de estimación y seguimiento', () => {
  it('envía la solicitud y abre la vista compartida del trabajo', async () => {
    vi.mocked(modelsService.getModelsByLake).mockResolvedValue([
      {
        id: MODEL_VERSION_ID,
        name: 'Modelo NDCI',
        version: '1.0',
        target_variable: 'chlorophyll_a',
        unit: 'ug/L',
        required_index: 'NDCI',
        status: 'VALIDATED',
        created_at: '2026-11-25T00:00:00Z',
      },
    ]);
    vi.mocked(executionsService.createJob).mockResolvedValue({
      job_id: JOB_ID,
      status: 'queued',
    });
    vi.mocked(executionsService.getJobStatus).mockResolvedValue({
      job_id: JOB_ID,
      job_type: 'estimation',
      status: 'completed',
      config: { model_id: MODEL_VERSION_ID, scene_id: SCENE_ID },
      result: null,
      dataset_version_id: null,
      model_version_id: MODEL_VERSION_ID,
      requested_by: '11111111-1111-4111-8111-111111111111',
      error_message: null,
      created_at: '2026-11-25T00:00:00Z',
      started_at: null,
      completed_at: '2026-11-25T00:00:01Z',
      updated_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/estimate']}>
        <Routes>
          <Route
            path="/estimate"
            element={<EstimationForm lakeId="lake-1" sceneId={SCENE_ID} />}
          />
          <Route
            path="/scientific/jobs/:jobId"
            element={<ScientificJobDetail />}
          />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(
      await screen.findByRole('button', { name: 'Generar Estimación' })
    );

    expect(
      await screen.findByText('Detalle del experimento')
    ).toBeInTheDocument();
    expect(await screen.findByText('Completado')).toBeInTheDocument();
    expect(
      screen.getByText('ID del trabajo').closest('.detail')
    ).toHaveTextContent(JOB_ID);
   expect(executionsService.createJob).toHaveBeenCalledWith({
      job_type: 'ESTIMATION',
      config: {
        model_id: MODEL_VERSION_ID,
        model_name: 'Modelo NDCI',
        scene_id: SCENE_ID,
      },
    });
    await waitFor(() => {
      expect(executionsService.getJobStatus).toHaveBeenCalledWith(
        JOB_ID,
        expect.any(AbortSignal)
      );
    });
  });
});
